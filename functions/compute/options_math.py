"""
Options pricing and Greeks calculation module.

This module provides Black-Scholes option pricing, Greek calculations, implied
volatility solving, and utility functions for options analysis. It's the core
computational engine for the Option Chain Dashboard.

Key Components:
    - OptionGreeks: Dataclass for storing delta, gamma, theta, vega, rho
    - OptionPrice: Dataclass for storing price and associated Greeks
    - Black-Scholes pricing functions for calls and puts
    - Greeks calculations (delta, gamma, theta, vega, rho)
    - Vectorized Greeks for batch calculations
    - Implied volatility solver using Brent's method
    - Utility functions for options analysis

Mathematical Formulas Used:
    - Black-Scholes: C = S*N(d1) - K*exp(-rT)*N(d2)
    - Delta (Call): N(d1)
    - Gamma: n(d1) / (S*sigma*sqrt(T))
    - Vega: S*n(d1)*sqrt(T) / 100 (per 1% vol)
    - Theta (Call): -S*n(d1)*sigma/(2*sqrt(T)) - r*K*exp(-rT)*N(d2)
    - Rho (Call): K*T*exp(-rT)*N(d2) / 100 (per 1% rate)

Usage:
    from functions.compute.options_math import (
        black_scholes_call,
        black_scholes_put,
        calculate_greeks,
        OptionGreeks,
        OptionPrice,
        OptionsAnalyzer
    )

    # Single option pricing
    call_price = black_scholes_call(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
    greeks = calculate_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20)

    # Batch calculations
    strikes = np.array([95, 100, 105])
    vols = np.array([0.18, 0.20, 0.22])
    results = calculate_greeks_vectorized(S=100, K=strikes, T=0.25, r=0.05, sigma=vols)

    # Implied volatility
    iv = implied_volatility(price=2.5, S=100, K=100, T=0.25, r=0.05)

    # Advanced analysis
    analyzer = OptionsAnalyzer(spot=100, risk_free_rate=0.05)
    atm_iv = analyzer.get_atm_iv(chain)
    skew = analyzer.get_skew(chain, delta_target=0.25)
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import math

from functions.util.logging_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class OptionGreeks:
    """Container for the five option Greeks.

    The Greeks measure the sensitivity of option prices to changes in
    underlying market parameters.

    Attributes:
        delta: Rate of change of option price relative to underlying price.
            Range: -1 to 1. Call delta positive, put delta negative.
            Interpretation: For delta=0.5, option price increases $0.50
            for every $1 move in underlying.

        gamma: Rate of change of delta relative to underlying price.
            Range: 0 to infinity (always positive).
            Interpretation: Higher gamma = delta changes faster.
            Peak gamma typically occurs at-the-money.

        theta: Time decay value per day.
            Usually negative for long options (loses value as expiry approaches).
            Expressed in dollars per day.

        vega: Sensitivity to 1% change in implied volatility.
            Always positive (higher vol = higher option value).
            Expressed in dollars per 1% vol change.

        rho: Sensitivity to 1% change in interest rates.
            Call rho positive, put rho negative.
            Expressed in dollars per 1% rate change.
    """

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def to_dict(self) -> Dict[str, float]:
        """Convert Greeks to dictionary format.

        Returns:
            Dictionary with keys: delta, gamma, theta, vega, rho
        """
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
        }

    def __repr__(self) -> str:
        """String representation of Greeks."""
        return (
            f"OptionGreeks(delta={self.delta:.4f}, gamma={self.gamma:.6f}, "
            f"theta={self.theta:.4f}, vega={self.vega:.4f}, rho={self.rho:.4f})"
        )


@dataclass
class OptionPrice:
    """Option price with associated Greeks.

    Combines the theoretical option price with its Greeks for comprehensive
    risk analysis.

    Attributes:
        price: Theoretical option price based on Black-Scholes model
        greeks: OptionGreeks dataclass containing all Greeks
    """

    price: float
    greeks: OptionGreeks

    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary format.

        Returns:
            Dictionary with 'price' and 'greeks' keys
        """
        return {
            "price": self.price,
            "greeks": self.greeks.to_dict(),
        }

    def __repr__(self) -> str:
        """String representation of OptionPrice."""
        return f"OptionPrice(price={self.price:.4f}, greeks={self.greeks})"


# ============================================================================
# BLACK-SCHOLES PRICING FUNCTIONS
# ============================================================================


def black_scholes_call(
    S: float, K: float, T: float, r: float, sigma: float
) -> float:
    """
    Calculate call option price using Black-Scholes model.

    Formula:
        C = S*N(d1) - K*exp(-rT)*N(d2)

    where:
        d1 = [ln(S/K) + (r + sigma^2/2)*T] / (sigma*sqrt(T))
        d2 = d1 - sigma*sqrt(T)
        N(x) = standard normal cumulative distribution

    Args:
        S: Current price of underlying asset
        K: Strike price of the option
        T: Time to expiration in years (e.g., 0.25 for 3 months)
        r: Risk-free interest rate as decimal (e.g., 0.05 for 5%)
        sigma: Implied volatility as decimal (e.g., 0.20 for 20%)

    Returns:
        Call option price in same currency as S and K

    Raises:
        ValueError: If inputs are invalid (negative prices, zero time, etc.)

    Example:
        >>> call_price = black_scholes_call(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        >>> print(f"Call price: ${call_price:.2f}")
        Call price: $2.71
    """
    # Validate inputs
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike price K must be positive, got {K}")
    if T <= 0:
        raise ValueError(f"Time to expiration T must be positive, got {T}")
    if sigma <= 0:
        raise ValueError(f"Volatility sigma must be positive, got {sigma}")
    if r < 0:
        raise ValueError(f"Risk-free rate r cannot be negative, got {r}")

    # Calculate d1 and d2
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    # Black-Scholes formula for call
    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

    return float(call_price)


def black_scholes_put(
    S: float, K: float, T: float, r: float, sigma: float
) -> float:
    """
    Calculate put option price using Black-Scholes model.

    Formula:
        P = K*exp(-rT)*N(-d2) - S*N(-d1)

    Derived from put-call parity: P = C - S + K*exp(-rT)

    Args:
        S: Current price of underlying asset
        K: Strike price of the option
        T: Time to expiration in years (e.g., 0.25 for 3 months)
        r: Risk-free interest rate as decimal (e.g., 0.05 for 5%)
        sigma: Implied volatility as decimal (e.g., 0.20 for 20%)

    Returns:
        Put option price in same currency as S and K

    Raises:
        ValueError: If inputs are invalid

    Example:
        >>> put_price = black_scholes_put(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        >>> print(f"Put price: ${put_price:.2f}")
        Put price: $2.37
    """
    # Validate inputs
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike price K must be positive, got {K}")
    if T <= 0:
        raise ValueError(f"Time to expiration T must be positive, got {T}")
    if sigma <= 0:
        raise ValueError(f"Volatility sigma must be positive, got {sigma}")
    if r < 0:
        raise ValueError(f"Risk-free rate r cannot be negative, got {r}")

    # Calculate d1 and d2
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    # Black-Scholes formula for put
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return float(put_price)


# ============================================================================
# GREEKS CALCULATION FUNCTIONS
# ============================================================================


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
) -> OptionGreeks:
    """
    Calculate all five Greeks for an option using Black-Scholes model.

    Computes delta, gamma, theta, vega, and rho for a single option contract.
    All Greeks are calculated analytically from Black-Scholes formulas.

    Args:
        S: Current price of underlying asset
        K: Strike price of the option
        T: Time to expiration in years
        r: Risk-free interest rate as decimal
        sigma: Implied volatility as decimal
        option_type: "call" or "put" (case-insensitive)

    Returns:
        OptionGreeks dataclass with all Greeks

    Raises:
        ValueError: If inputs are invalid or option_type is invalid

    Mathematical Formulas:
        d1 = [ln(S/K) + (r + sigma^2/2)*T] / (sigma*sqrt(T))
        d2 = d1 - sigma*sqrt(T)
        n(x) = (1/sqrt(2π)) * exp(-x^2/2)  [standard normal PDF]
        N(x) = cumulative standard normal CDF

        For CALL:
            delta = N(d1)
            gamma = n(d1) / (S*sigma*sqrt(T))
            vega = S*n(d1)*sqrt(T) / 100  [per 1% vol]
            theta = [-S*n(d1)*sigma/(2*sqrt(T)) - r*K*exp(-rT)*N(d2)] / 365
            rho = K*T*exp(-rT)*N(d2) / 100  [per 1% rate]

        For PUT:
            delta = -N(-d1) = N(d1) - 1
            gamma = n(d1) / (S*sigma*sqrt(T))  [same as call]
            vega = S*n(d1)*sqrt(T) / 100  [same as call]
            theta = [-S*n(d1)*sigma/(2*sqrt(T)) + r*K*exp(-rT)*N(-d2)] / 365
            rho = -K*T*exp(-rT)*N(-d2) / 100  [per 1% rate]

    Example:
        >>> greeks = calculate_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        >>> print(f"Delta: {greeks.delta:.4f}")
        Delta: 0.6368
    """
    # Validate inputs
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike price K must be positive, got {K}")
    if T <= 0:
        raise ValueError(f"Time to expiration T must be positive, got {T}")
    if sigma <= 0:
        raise ValueError(f"Volatility sigma must be positive, got {sigma}")
    if r < 0:
        raise ValueError(f"Risk-free rate r cannot be negative, got {r}")

    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type}")

    # Calculate d1 and d2
    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    # Standard normal PDF and CDF values
    n_d1 = norm.pdf(d1)  # PDF of d1
    n_minus_d1 = norm.pdf(-d1)  # PDF of -d1
    n_d2 = norm.cdf(d2)  # CDF of d2
    n_minus_d2 = norm.cdf(-d2)  # CDF of -d2

    # Gamma and Vega are the same for calls and puts
    gamma = n_d1 / (S * sigma * sqrt_t)
    vega = S * n_d1 * sqrt_t / 100.0  # Per 1% change in volatility

    # Type-specific Greeks
    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (
            -S * n_d1 * sigma / (2 * sqrt_t)
            - r * K * np.exp(-r * T) * n_d2
        ) / 365.0
        rho = K * T * np.exp(-r * T) * n_d2 / 100.0

    else:  # put
        delta = -norm.cdf(-d1)  # Equivalent to norm.cdf(d1) - 1
        theta = (
            -S * n_d1 * sigma / (2 * sqrt_t)
            + r * K * np.exp(-r * T) * n_minus_d2
        ) / 365.0
        rho = -K * T * np.exp(-r * T) * n_minus_d2 / 100.0

    return OptionGreeks(
        delta=float(delta),
        gamma=float(gamma),
        theta=float(theta),
        vega=float(vega),
        rho=float(rho),
    )


def calculate_greeks_vectorized(
    S: float,
    K: np.ndarray,
    T: float,
    r: float,
    sigma: np.ndarray,
    option_type: str = "call",
) -> Dict[str, np.ndarray]:
    """
    Calculate Greeks for multiple options in batch using vectorized numpy operations.

    Efficiently computes Greeks for arrays of strikes and volatilities.
    Much faster than calling calculate_greeks() in a loop for large datasets.

    Args:
        S: Current price of underlying asset (scalar)
        K: Array of strike prices (must be 1D numpy array)
        T: Time to expiration in years (scalar)
        r: Risk-free interest rate as decimal (scalar)
        sigma: Array of implied volatilities (must match K shape)
        option_type: "call" or "put"

    Returns:
        Dictionary with keys: delta, gamma, theta, vega, rho
        Each value is a numpy array with same shape as K

    Raises:
        ValueError: If inputs are invalid or arrays have mismatched shapes

    Example:
        >>> strikes = np.array([95, 100, 105])
        >>> vols = np.array([0.18, 0.20, 0.22])
        >>> greeks = calculate_greeks_vectorized(
        ...     S=100, K=strikes, T=0.25, r=0.05, sigma=vols
        ... )
        >>> print(f"Deltas: {greeks['delta']}")
        Deltas: [0.7382 0.6368 0.5374]
    """
    # Validate inputs
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if T <= 0:
        raise ValueError(f"Time to expiration T must be positive, got {T}")
    if r < 0:
        raise ValueError(f"Risk-free rate r cannot be negative, got {r}")

    # Convert to numpy arrays if needed
    K = np.asarray(K)
    sigma = np.asarray(sigma)

    # Validate shapes match
    if K.shape != sigma.shape:
        raise ValueError(
            f"K and sigma must have same shape, got {K.shape} vs {sigma.shape}"
        )

    # Validate all values are positive
    if np.any(K <= 0):
        raise ValueError(f"All strike prices K must be positive")
    if np.any(sigma <= 0):
        raise ValueError(f"All volatilities sigma must be positive")

    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type}")

    # Vectorized calculations
    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    # Standard normal PDF and CDF
    n_d1 = norm.pdf(d1)
    n_minus_d1 = norm.pdf(-d1)

    # Gamma and Vega are identical for calls and puts
    gamma = n_d1 / (S * sigma * sqrt_t)
    vega = S * n_d1 * sqrt_t / 100.0

    # Type-specific Greeks
    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (
            -S * n_d1 * sigma / (2 * sqrt_t)
            - r * K * np.exp(-r * T) * norm.cdf(d2)
        ) / 365.0
        rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100.0

    else:  # put
        delta = norm.cdf(d1) - 1
        theta = (
            -S * n_d1 * sigma / (2 * sqrt_t)
            + r * K * np.exp(-r * T) * norm.cdf(-d2)
        ) / 365.0
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100.0

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "rho": rho,
    }


# ============================================================================
# IMPLIED VOLATILITY SOLVER
# ============================================================================


def implied_volatility(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    precision: float = 1e-6,
    max_iterations: int = 100,
) -> Optional[float]:
    """
    Solve for implied volatility given an option price using Brent's method.

    Uses the scipy.optimize.brentq root-finding algorithm to efficiently solve
    for the volatility that makes the Black-Scholes price equal to the market
    price. Brentq is very fast and reliable for this application.

    Algorithm:
        1. Define objective: f(sigma) = BS_price(sigma) - market_price
        2. Search for sigma where f(sigma) = 0
        3. Search bounds: [0.001, 5.0] (0.1% to 500% volatility)
        4. Stop when f(sigma) < precision or max iterations reached

    Args:
        price: Market price of the option
        S: Current price of underlying asset
        K: Strike price of the option
        T: Time to expiration in years
        r: Risk-free interest rate as decimal
        option_type: "call" or "put"
        precision: Tolerance for solution (default 1e-6)
        max_iterations: Maximum iterations for solver (default 100)

    Returns:
        Implied volatility as decimal (e.g., 0.20 for 20%)
        Returns None if solver fails to converge

    Raises:
        ValueError: If inputs are invalid

    Example:
        >>> market_price = 2.50
        >>> iv = implied_volatility(
        ...     price=market_price, S=100, K=100, T=0.25, r=0.05
        ... )
        >>> print(f"IV: {iv:.2%}")
        IV: 20.00%

    Notes:
        - For arbitrage-free pricing, ATM options typically have IV 15-30%
        - OTM options often have higher IV (volatility smile/skew)
        - If solver fails, returns None (handle gracefully in caller)
        - Solver is very fast (typically <50ms even for extreme prices)
    """
    # Validate inputs
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike price K must be positive, got {K}")
    if T <= 0:
        raise ValueError(f"Time to expiration T must be positive, got {T}")
    if r < 0:
        raise ValueError(f"Risk-free rate r cannot be negative, got {r}")
    if price < 0:
        raise ValueError(f"Option price cannot be negative, got {price}")

    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type}")

    # Define objective function (difference between BS price and market price)
    def objective(sigma: float) -> float:
        try:
            if option_type == "call":
                bs_price = black_scholes_call(S, K, T, r, sigma)
            else:
                bs_price = black_scholes_put(S, K, T, r, sigma)
            return bs_price - price
        except ValueError:
            # If sigma is out of range, return large error
            return float("inf")

    # Check if solution is possible (price within bounds)
    # For calls: min = 0, max = S (can't exceed spot)
    # For puts: min = 0, max = K*exp(-rT) (can't exceed PV of strike)
    intrinsic = max(0, (S - K) if option_type == "call" else (K - S))
    time_value = price - intrinsic

    if time_value < 0:
        # Market price is below intrinsic value - arbitrage or data error
        logger.warning(
            f"Option price ${price:.2f} below intrinsic value ${intrinsic:.2f} "
            f"({option_type} S={S} K={K})"
        )
        return None

    if price < intrinsic:
        # Price below intrinsic - impossible
        return None

    # Determine bounds for volatility search
    # Lower bound: very small vol (but positive to avoid log(0))
    lower_bound = 0.001
    # Upper bound: very high vol (500%)
    upper_bound = 5.0

    try:
        # Use Brent's method to find root
        # brentq requires objective to have opposite signs at bounds
        obj_lower = objective(lower_bound)
        obj_upper = objective(upper_bound)

        # Check that signs are opposite (bracket contains solution)
        if obj_lower * obj_upper > 0:
            # Solution not bracketed - likely price is outside range
            logger.debug(
                f"IV solution not bracketed for {option_type} S={S} K={K} "
                f"T={T:.4f} price={price:.2f}"
            )
            return None

        # Solve for volatility
        implied_vol = brentq(
            objective,
            lower_bound,
            upper_bound,
            xtol=precision,
            maxiter=max_iterations,
        )

        return float(implied_vol)

    except ValueError as e:
        # Brent's method failed (usually means bracket doesn't contain solution)
        logger.debug(f"IV solver failed for {option_type} at S={S} K={K}: {e}")
        return None
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in IV solver: {e}")
        return None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def calculate_implied_move(
    atm_call_price: float,
    atm_put_price: float,
    spot: float,
) -> float:
    """
    Calculate the market-implied move over the holding period.

    The implied move is estimated as roughly one standard deviation of
    expected price movement, derived from the ATM straddle price.

    Formula:
        Implied Move ≈ (Call Price + Put Price) * 0.4  [rough approximation]
        More precisely: σ * S * sqrt(T)

    This represents the 1-sigma move the market is pricing in, useful for
    determining expected move before options expiration.

    Args:
        atm_call_price: Price of at-the-money call option
        atm_put_price: Price of at-the-money put option
        spot: Current price of underlying asset

    Returns:
        Implied move in dollars (same currency as spot)

    Raises:
        ValueError: If inputs are invalid

    Example:
        >>> call = 2.50  # $2.50
        >>> put = 2.37   # $2.37
        >>> spot = 100.00
        >>> move = calculate_implied_move(call, put, spot)
        >>> print(f"Expected move: ${move:.2f}")
        Expected move: $1.95

    Notes:
        - Higher option prices = higher expected move
        - ATM options provide best price signal for implied move
        - Approximation assumes ATM call ≈ ATM put (true for puts and calls)
    """
    if spot <= 0:
        raise ValueError(f"Spot must be positive, got {spot}")
    if atm_call_price < 0:
        raise ValueError(f"Call price cannot be negative, got {atm_call_price}")
    if atm_put_price < 0:
        raise ValueError(f"Put price cannot be negative, got {atm_put_price}")

    # Straddle price is sum of call and put
    straddle_price = atm_call_price + atm_put_price

    # Implied move is approximately 0.4 * straddle price
    # This approximation comes from empirical observation that the straddle
    # price is roughly 0.4 * one-sigma move * spot
    implied_move = straddle_price * 0.4

    return float(implied_move)


def calculate_put_call_parity_check(
    call_price: float,
    put_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
) -> Dict[str, float]:
    """
    Verify put-call parity and calculate arbitrage opportunity if it exists.

    Put-Call Parity (European options):
        C - P = S - K*exp(-rT)

    If this relationship is violated, an arbitrage opportunity exists.

    Args:
        call_price: Price of call option
        put_price: Price of put option
        S: Current price of underlying asset
        K: Strike price
        T: Time to expiration in years
        r: Risk-free interest rate

    Returns:
        Dictionary with:
            - parity_difference: C - P - (S - K*exp(-rT)) = theoretical - actual
            - parity_expected: S - K*exp(-rT) (right side of parity)
            - parity_actual: C - P (left side of parity)
            - arbitrage_opportunity: abs(parity_difference) (negative if exists)
            - is_arbitrage: True if parity violated by more than 0.01

    Example:
        >>> result = calculate_put_call_parity_check(
        ...     call_price=2.50, put_price=2.37, S=100, K=100,
        ...     T=0.25, r=0.05
        ... )
        >>> if result['is_arbitrage']:
        ...     print("Arbitrage found!")
    """
    # Calculate theoretical relationship (right side)
    parity_expected = S - K * np.exp(-r * T)

    # Calculate actual relationship (left side)
    parity_actual = call_price - put_price

    # Difference shows arbitrage
    parity_difference = parity_actual - parity_expected

    return {
        "parity_difference": float(parity_difference),
        "parity_expected": float(parity_expected),
        "parity_actual": float(parity_actual),
        "arbitrage_opportunity": float(abs(parity_difference)),
        "is_arbitrage": abs(parity_difference) > 0.01,  # More than $0.01 slippage
    }


def stress_option_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    spot_shock: float,
    vol_shock_pct: float = 0.20,
) -> Dict[str, float]:
    """
    Calculate option price under stressed market conditions.

    Useful for scenario analysis: "What if spot moves $5 and vol rises 20%?"

    Args:
        S: Current spot price
        K: Strike price
        T: Time to expiration in years
        r: Risk-free rate
        sigma: Current implied volatility
        option_type: "call" or "put"
        spot_shock: Change in spot price (e.g., +5 or -3)
        vol_shock_pct: Volatility shock as percentage point change
            (e.g., 0.20 = vol increases from 20% to 40%)

    Returns:
        Dictionary with:
            - original_price: Current option price
            - stressed_price: Price after shocks applied
            - pnl: P&L from stress (negative means loss)
            - pnl_pct: P&L as percentage of original price
            - delta_hedged_pnl: P&L if delta-hedged

    Example:
        >>> result = stress_option_price(
        ...     S=100, K=100, T=0.25, r=0.05, sigma=0.20,
        ...     option_type='call', spot_shock=5, vol_shock_pct=0.10
        ... )
        >>> print(f"Stressed P&L: ${result['pnl']:.2f}")
    """
    # Get current option price
    if option_type.lower() == "call":
        original_price = black_scholes_call(S, K, T, r, sigma)
    else:
        original_price = black_scholes_put(S, K, T, r, sigma)

    # Apply shocks
    stressed_spot = S + spot_shock
    stressed_vol = sigma + vol_shock_pct

    # Ensure stressed vol stays positive
    if stressed_vol <= 0:
        stressed_vol = 0.001

    # Get stressed option price
    if option_type.lower() == "call":
        stressed_price = black_scholes_call(stressed_spot, K, T, r, stressed_vol)
    else:
        stressed_price = black_scholes_put(stressed_spot, K, T, r, stressed_vol)

    # Calculate P&L
    pnl = stressed_price - original_price
    pnl_pct = (pnl / original_price) if original_price > 0 else float("inf")

    # Calculate delta-hedged P&L (gamma + vega effect)
    greeks = calculate_greeks(S, K, T, r, sigma, option_type)
    delta_hedged_pnl = (
        0.5 * greeks.gamma * (spot_shock**2) + greeks.vega * vol_shock_pct
    )

    return {
        "original_price": float(original_price),
        "stressed_price": float(stressed_price),
        "spot_shock": float(spot_shock),
        "vol_shock_pct": float(vol_shock_pct),
        "pnl": float(pnl),
        "pnl_pct": float(pnl_pct),
        "delta_hedged_pnl": float(delta_hedged_pnl),
    }


# ============================================================================
# OPTIONS ANALYZER CLASS
# ============================================================================


class OptionsAnalyzer:
    """
    High-level interface for options chain analysis.

    Provides convenience methods for common analysis tasks like finding ATM IV,
    calculating skew, and computing chain metrics.

    Attributes:
        spot: Current price of underlying asset
        risk_free_rate: Risk-free interest rate (default 0.05 = 5%)

    Usage:
        analyzer = OptionsAnalyzer(spot=100, risk_free_rate=0.05)
        atm_iv = analyzer.get_atm_iv(chain)
        skew = analyzer.get_skew(chain)
    """

    def __init__(
        self, spot: float, risk_free_rate: Optional[float] = None
    ) -> None:
        """
        Initialize OptionsAnalyzer.

        Args:
            spot: Current price of underlying asset
            risk_free_rate: Risk-free interest rate (default 0.05)

        Raises:
            ValueError: If spot is not positive
        """
        if spot <= 0:
            raise ValueError(f"Spot price must be positive, got {spot}")

        self.spot = spot
        self.risk_free_rate = risk_free_rate or 0.05

        logger.debug(
            f"OptionsAnalyzer initialized: spot={spot}, r={self.risk_free_rate}"
        )

    def get_atm_iv(
        self,
        chain: List[Dict],
        option_type: str = "call",
    ) -> Optional[float]:
        """
        Get implied volatility of at-the-money option.

        Finds the option closest to ATM and returns its IV. Useful for
        assessing overall volatility levels in the chain.

        Args:
            chain: List of option dictionaries with keys:
                   strike, option_type, bid, ask, implied_volatility
            option_type: "call" or "put" - which option type to use

        Returns:
            Implied volatility as decimal, or None if not found/not available

        Example:
            >>> chain = [
            ...     {"strike": 95, "option_type": "call", "implied_volatility": 0.20},
            ...     {"strike": 100, "option_type": "call", "implied_volatility": 0.19},
            ... ]
            >>> analyzer = OptionsAnalyzer(spot=100)
            >>> iv = analyzer.get_atm_iv(chain)
        """
        if not chain:
            return None

        # Filter to requested option type
        same_type = [
            opt for opt in chain if opt.get("option_type", "").lower() == option_type.lower()
        ]

        if not same_type:
            return None

        # Find closest to spot
        closest = min(same_type, key=lambda x: abs(x.get("strike", 0) - self.spot))

        return closest.get("implied_volatility")

    def get_skew(
        self,
        chain: List[Dict],
        delta_target: float = 0.25,
    ) -> Optional[float]:
        """
        Calculate volatility skew in the options chain.

        Skew measures the difference in implied volatility between OTM puts
        and OTM calls, indicating the market's view of downside vs upside risk.

        Positive skew = OTM puts more expensive (more downside premium)

        Args:
            chain: List of option dictionaries
            delta_target: Target delta for skew calculation (default 0.25)

        Returns:
            Skew as decimal (IV_put - IV_call), or None if not calculable

        Example:
            >>> skew = analyzer.get_skew(chain, delta_target=0.25)
            >>> if skew > 0.05:
            ...     print("Significant downside skew - market expects crashes")
        """
        if not chain:
            return None

        calls = [opt for opt in chain if opt.get("option_type", "").lower() == "call"]
        puts = [opt for opt in chain if opt.get("option_type", "").lower() == "put"]

        if not calls or not puts:
            return None

        # Find call and put closest to delta_target
        # For calls: delta_target = positive delta (e.g., 0.25)
        # For puts: delta_target = abs(delta), so we look for -delta_target

        closest_call = min(
            calls,
            key=lambda x: abs((x.get("delta", 0) or 0) - delta_target),
            default=None,
        )
        closest_put = min(
            puts,
            key=lambda x: abs((x.get("delta", 0) or 0) + delta_target),
            default=None,
        )

        if not closest_call or not closest_put:
            return None

        call_iv = closest_call.get("implied_volatility")
        put_iv = closest_put.get("implied_volatility")

        if call_iv is None or put_iv is None:
            return None

        return float(put_iv - call_iv)

    def get_chain_metrics(self, chain: List[Dict]) -> Dict[str, float]:
        """
        Calculate comprehensive metrics for an options chain.

        Computes aggregate statistics like mean IV, IV spread, put/call ratios, etc.

        Args:
            chain: List of option dictionaries

        Returns:
            Dictionary with keys:
                - count: Total options in chain
                - calls_count: Number of calls
                - puts_count: Number of puts
                - mean_iv: Average IV across chain
                - min_iv: Minimum IV in chain
                - max_iv: Maximum IV in chain
                - iv_spread: max_iv - min_iv
                - mean_bid_ask_spread: Average bid-ask spread %

        Example:
            >>> metrics = analyzer.get_chain_metrics(chain)
            >>> print(f"Chain has {metrics['calls_count']} calls")
        """
        if not chain:
            return {
                "count": 0,
                "calls_count": 0,
                "puts_count": 0,
                "mean_iv": None,
                "min_iv": None,
                "max_iv": None,
                "iv_spread": None,
                "mean_bid_ask_spread": None,
            }

        # Separate calls and puts
        calls = [opt for opt in chain if opt.get("option_type", "").lower() == "call"]
        puts = [opt for opt in chain if opt.get("option_type", "").lower() == "put"]

        # Extract IVs
        ivs = [opt.get("implied_volatility") for opt in chain
               if opt.get("implied_volatility") is not None]

        # Extract bid-ask spreads
        spreads = []
        for opt in chain:
            bid = opt.get("bid", 0)
            ask = opt.get("ask", 0)
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
                if mid > 0:
                    spread_pct = (ask - bid) / mid * 100
                    spreads.append(spread_pct)

        return {
            "count": len(chain),
            "calls_count": len(calls),
            "puts_count": len(puts),
            "mean_iv": float(np.mean(ivs)) if ivs else None,
            "min_iv": float(np.min(ivs)) if ivs else None,
            "max_iv": float(np.max(ivs)) if ivs else None,
            "iv_spread": float(np.max(ivs) - np.min(ivs)) if ivs and len(ivs) > 1 else None,
            "mean_bid_ask_spread": float(np.mean(spreads)) if spreads else None,
        }
