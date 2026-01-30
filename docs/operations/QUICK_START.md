# Option Chain Dashboard - Quick Start Guide

**Status**: ✅ Complete and ready to run!
**Backend**: Python + FastAPI on port 8061
**Frontend**: React on port 8060
**Time to run**: 5 minutes

---

## 🚀 Start Everything in 3 Commands

### Terminal 1: Backend API + Scheduler
```bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
source venv/bin/activate
python main.py --demo-mode
```

Output:
```
[2026-01-26 21:15:00.000 UTC] [INFO] Initializing database...
[2026-01-26 21:15:00.100 UTC] [INFO] Starting scheduler...
[2026-01-26 21:15:00.200 UTC] [INFO] Starting FastAPI on port 8061...
[2026-01-26 21:15:00.300 UTC] [INFO] All systems running. Press Ctrl+C to shutdown.
```

### Terminal 2: Frontend
```bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend
npm run dev
```

Output:
```
vite v5.0.0 build 0.00s, scaffolding complete.

➜  local:   http://localhost:8060/
➜  press h to show help
```

### Terminal 3: View in Browser
```bash
# Open this in your browser:
http://localhost:8060
```

**You're done!** 🎉

---

## 📍 What You'll See

### Dashboard (http://localhost:8060)
- Overview with metrics
- Recent alerts
- System status
- Scan trigger button

### Navigation (Left Sidebar)
- 🏠 Dashboard
- 🔔 Alert Feed
- 📊 Option Chains
- 💡 Strategy Explorer
- ⚙️ Configuration

---

## ✅ Verify Everything Works

### Check Backend
```bash
curl http://localhost:8061/health
# Should return: {"status": "ok", "timestamp": "2026-01-26T21:15:00Z"}

curl http://localhost:8061/alerts/latest?limit=5
# Should return: list of recent alerts (empty if fresh start)
```

### Check Frontend
Visit http://localhost:8060
- Should show dashboard with metrics
- Green health indicator in header
- No console errors in browser (F12)

---

## 🔧 Common Tasks

### Trigger a Scan
```bash
curl -X POST http://localhost:8061/scan/run
# Returns: {"scan_id": 1, "status": "running"}
```

### View Latest Alerts
```bash
curl http://localhost:8061/alerts/latest?limit=10 | python -m json.tool
```

### Check Scan Status
```bash
curl http://localhost:8061/scan/status/1 | python -m json.tool
```

### View Configuration
Visit http://localhost:8060/config in browser

### View API Documentation
Visit http://localhost:8061/docs in browser (Swagger UI)

---

## 🛑 Stop Everything

```bash
# Terminal 1 (Backend)
Ctrl+C

# Terminal 2 (Frontend)
Ctrl+C
```

---

## 📚 Documentation

- **Backend**: See `IMPLEMENTATION_SUMMARY.md`
- **Frontend**: See `frontend/REACT_IMPLEMENTATION_SUMMARY.md`
- **Full Details**: See `PROJECT_COMPLETE.md`
- **Development**: See `CLAUDE.md`

---

## ⚙️ Configuration

Edit `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/config.yaml`

Key settings:
- `detectors`: Enable/disable detectors
- `risk_free_rate`: For options pricing
- `max_alerts_per_day`: Rate limiting
- `collection_times_et`: When to scan (default: 16:15 = 4:15 PM ET post-close)

---

## 🧪 Test the System

```bash
# 1. Open Dashboard
http://localhost:8060

# 2. Manually trigger scan
curl -X POST http://localhost:8061/scan/run

# 3. Wait 30-60 seconds for scan to complete

# 4. View alerts in Dashboard or visit
http://localhost:8060/alerts

# 5. Click on alert to see ticker details
http://localhost:8060/ticker/SOFI

# 6. Explore option chains
http://localhost:8060/options

# 7. Learn strategies
http://localhost:8060/strategies

# 8. Check system health
http://localhost:8060/config
```

---

## 🎯 Demo Mode Notes

The system starts in **Demo Mode** by default with synthetic data:
- All prices generated with realistic random walks
- IV curves match real market conditions
- Option chains have 3 expirations per ticker
- Perfect for testing without API limits

Switch to **Production Mode** in `/config` page (requires backend restart)

---

## 📊 Architecture (Quick Overview)

```
Browser (Port 8060)
    ↓ (HTTP/HTTPS)
Vite Dev Server
    ↓ (API proxy to 8061)
FastAPI Backend (Port 8061)
    ↓
Business Logic (functions/)
    ↓
DuckDB Database (data/oor.duckdb)
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8060 already in use | `lsof -i :8060` → kill process → restart |
| Port 8061 already in use | `lsof -i :8061` → kill process → restart |
| Backend won't start | Check `logs/option_chain_dashboard.log` for errors |
| Frontend won't load | Check browser console (F12) for errors |
| API calls failing | Verify backend is running: `curl http://localhost:8061/health` |
| Alerts not appearing | Try `curl -X POST http://localhost:8061/scan/run` |

---

## 🔗 Useful Links

- **Dashboard**: http://localhost:8060
- **API Docs**: http://localhost:8061/docs (Swagger)
- **API ReDoc**: http://localhost:8061/redoc (ReDoc)
- **Health Check**: http://localhost:8061/health
- **Config Page**: http://localhost:8060/config

---

## ✨ Key Features

### Backend
✅ Real-time options analysis
✅ 6 intelligent detectors
✅ Alert scoring & throttling
✅ Portfolio risk enforcement
✅ 24/7 unattended operation
✅ UTC timestamps & crash recovery

### Frontend
✅ 6 full-featured pages
✅ Real-time API integration
✅ Dark mode UI
✅ Responsive design
✅ Interactive charts
✅ Strategy explorer

---

## 📖 Next Steps

1. **Explore Dashboard** - Get familiar with the UI
2. **View Alerts** - See what detectors are finding
3. **Check Config** - Understand system settings
4. **Read Strategies** - Learn about options strategies
5. **Review Documentation** - Dive deeper into architecture
6. **Customize Config** - Adjust thresholds for your needs

---

## 🎓 Learning Path

### 15 minutes
1. Start system (backend + frontend)
2. Explore Dashboard page
3. Trigger a scan
4. View generated alerts

### 30 minutes
1. Browse AlertFeed with filters
2. Click through to ticker details
3. Explore OptionChains page
4. View system configuration

### 1 hour
1. Read PROJECT_COMPLETE.md for full overview
2. Review API endpoints in Swagger docs
3. Check logs for detailed operation
4. Experiment with different configurations

### Ongoing
1. Customize config.yaml for your watchlist
2. Adjust detector thresholds
3. Run backtests with historized data
4. Integrate with external systems

---

## 💡 Pro Tips

- **Demo Mode**: Perfect for testing without API limits
- **Logs**: Check `logs/` folder for detailed diagnostics
- **API**: Use `/docs` endpoint for interactive API testing
- **Config Reload**: No restart needed - configs auto-reload
- **CSV Export**: Export alerts from AlertFeed page
- **Dark Mode**: Default - no light mode needed!

---

## 🆘 Need Help?

1. Check logs: `tail -f logs/option_chain_dashboard.log`
2. Read CLAUDE.md for development setup
3. Review PROJECT_COMPLETE.md for full documentation
4. Check API docs: http://localhost:8061/docs
5. Test with curl (examples above)

---

**You're all set! Enjoy Option Chain Dashboard! 🚀**

Questions? Check the comprehensive documentation:
- **Backend docs**: `IMPLEMENTATION_SUMMARY.md`
- **Frontend docs**: `frontend/REACT_IMPLEMENTATION_SUMMARY.md`
- **Full overview**: `PROJECT_COMPLETE.md`
