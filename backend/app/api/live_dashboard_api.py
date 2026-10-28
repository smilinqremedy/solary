import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.services.live_telemetry_simulator import live_simulator
from app.services.rules_engine import rules_engine
from app.services.analytics_service import analytics_service
from app.services.whatsapp_service import whatsapp_service
from app.config import settings

router = APIRouter(tags=["Live Progress & Dashboard"])

class ScenarioRequest(BaseModel):
    scenario: str

class ChatRequest(BaseModel):
    message: str

@router.get("/api/v1/live/status")
async def get_live_status():
    """Returns the comprehensive real-time edge & cloud intelligence status."""
    tel = live_simulator.get_current_telemetry()
    
    # Calculate real-time depletion
    depletion_hours = rules_engine.calculate_depletion_time_hours(
        battery_capacity_wh=10000.0,
        current_soc_pct=float(tel["bat_soc"]),
        cutoff_soc_pct=10.0,
        active_load_w=float(tel["load_w"])
    )

    # Calculate real-time savings
    savings = analytics_service.calculate_generator_fuel_savings(
        kwh_generated=18.5 + (live_simulator.step * 0.01),
        fuel_price_ngn=settings.DEFAULT_FUEL_PRICE_NAIRA_PER_LITER
    )

    return {
        "telemetry": tel,
        "depletion": {
            "hours": round(depletion_hours, 2),
            "human": rules_engine.format_hours_minutes(depletion_hours),
            "is_critical": (not tel["grid_on"]) and tel["pv_w"] < 200 and tel["bat_soc"] < 40 and tel["load_w"] > 1500
        },
        "savings": savings,
        "alerts": live_simulator.recent_alerts[-5:],
        "chat_history": live_simulator.chat_history[-10:],
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@router.post("/api/v1/live/scenario")
async def trigger_live_scenario(req: ScenarioRequest):
    """Injects a real-world Nigerian power scenario into the running simulator."""
    result_msg = live_simulator.set_scenario(req.scenario)
    return {"status": "success", "scenario": req.scenario, "message": result_msg}

@router.post("/api/v1/live/chat")
async def chat_with_bot(req: ChatRequest):
    """Simulates an interactive WhatsApp conversation with the Meta Cloud API bot."""
    user_msg = req.message.strip()
    tel = live_simulator.get_current_telemetry()
    
    # Record user message in live chat
    live_simulator.chat_history.append({
        "sender": "user",
        "time": datetime.now().strftime("%H:%M:%S"),
        "text": user_msg
    })

    device_info = {
        "site_name": "Lekki Phase 1 Residential Hybrid",
        "battery_type": "LiFePO4 (48V 200Ah)",
        "battery_capacity_wh": 10000.0
    }
    analytics_summary = await analytics_service.get_daily_energy_summary(live_simulator.device_id)

    bot_reply = await whatsapp_service.handle_conversational_query(
        sender_phone="+2348031234567",
        message_body=user_msg,
        latest_telemetry=tel,
        device_info=device_info,
        analytics_summary=analytics_summary
    )

    live_simulator.chat_history.append({
        "sender": "bot",
        "time": datetime.now().strftime("%H:%M:%S"),
        "text": bot_reply
    })

    return {"user_message": user_msg, "bot_reply": bot_reply}

@router.get("/api/v1/live/stream")
async def live_telemetry_sse(request: Request):
    """Server-Sent Events (SSE) pushing 1-second live telemetry updates to the dashboard."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            data = await get_live_status()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the rich, real-time live energy intelligence web dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML_TEMPLATE, status_code=200)

DASHBOARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Solary - Live Solar Energy Intelligence & WhatsApp Alerting</title>
    <!-- TailwindCSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Lucide Icons CDN -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        @keyframes pulse-flow {
            0% { opacity: 0.3; transform: scale(0.98); }
            50% { opacity: 1; transform: scale(1.02); }
            100% { opacity: 0.3; transform: scale(0.98); }
        }
        .flow-active {
            animation: pulse-flow 2s infinite ease-in-out;
        }
        .custom-scrollbar::-webkit-scrollbar {
            width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
            background-color: #334155;
            border-radius: 9999px;
        }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen flex flex-col">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <i data-lucide="sun" class="w-6 h-6 text-slate-950"></i>
            </div>
            <div>
                <h1 class="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                    Solary
                    <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">LIVE PRODUCTION</span>
                </h1>
                <p class="text-xs text-slate-400">Solary IoT Edge Gateway • Modbus RTU (Growatt/Must) • Meta WhatsApp Cloud API</p>
            </div>
        </div>

        <div class="flex items-center space-x-4">
            <div class="flex items-center space-x-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                <span class="font-mono text-slate-300" id="server-time">Syncing...</span>
            </div>
            <div class="flex items-center space-x-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
                <span class="text-slate-400">Device:</span>
                <span class="font-mono font-semibold text-emerald-400">NG-INV-00124</span>
            </div>
            <div id="wifi-badge" class="flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-400">
                <i data-lucide="wifi" class="w-3.5 h-3.5"></i>
                <span id="wifi-status-text">Wi-Fi Online</span>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

        <!-- Banner Alert Box (Critical Load Warning) -->
        <div id="critical-alert-box" class="hidden p-4 rounded-xl border border-red-500/50 bg-red-950/40 text-red-200 flex items-start space-x-4 shadow-xl shadow-red-950/50 animate-pulse">
            <i data-lucide="alert-triangle" class="w-6 h-6 text-red-400 shrink-0 mt-0.5"></i>
            <div class="flex-1">
                <h3 class="font-bold text-red-300">🚨 CRITICAL BATTERY DEPLETION ALERT ACTIVE</h3>
                <p class="text-sm text-red-200/90 mt-0.5">Grid is DOWN and high inductive load is detected. Battery will deplete to cutoff in <span id="alert-depletion-time" class="font-bold underline">--</span>! Turn off ACs and pumps immediately.</p>
            </div>
            <span class="text-xs px-2.5 py-1 rounded bg-red-500/20 text-red-300 border border-red-500/30 uppercase font-bold tracking-wider">30-min Cooldown</span>
        </div>

        <!-- Metric Cards Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <!-- Card 1: Grid (NEPA) -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-slate-700">
                <div class="flex justify-between items-start">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Grid Power (NEPA)</span>
                    <span id="grid-status-badge" class="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">AVAILABLE</span>
                </div>
                <div class="mt-4 flex items-baseline space-x-2">
                    <span id="grid-v" class="text-3xl font-extrabold text-white">226.4</span>
                    <span class="text-sm font-semibold text-slate-400">Volts AC</span>
                </div>
                <p class="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
                    <i data-lucide="activity" class="w-3.5 h-3.5"></i>
                    Frequency: 50.0 Hz • 1-Phase
                </p>
                <div class="absolute -right-2 -bottom-2 opacity-5 pointer-events-none">
                    <i data-lucide="zap" class="w-24 h-24 text-white"></i>
                </div>
            </div>

            <!-- Card 2: Solar PV Generation -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-slate-700">
                <div class="flex justify-between items-start">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Solar Array (PV)</span>
                    <span class="px-2 py-0.5 rounded text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">HARVESTING</span>
                </div>
                <div class="mt-4 flex items-baseline space-x-2">
                    <span id="pv-w" class="text-3xl font-extrabold text-amber-400">2,650</span>
                    <span class="text-sm font-semibold text-slate-400">Watts</span>
                </div>
                <p class="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
                    <i data-lucide="sun-dim" class="w-3.5 h-3.5"></i>
                    PV Voltage: <span id="pv-v" class="text-slate-300 font-mono">76.2 V</span>
                </p>
                <div class="absolute -right-2 -bottom-2 opacity-5 pointer-events-none">
                    <i data-lucide="sun" class="w-24 h-24 text-amber-400"></i>
                </div>
            </div>

            <!-- Card 3: Battery Storage -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-slate-700">
                <div class="flex justify-between items-start">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Battery Bank</span>
                    <span id="bat-mode-badge" class="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">⚡ CHARGING</span>
                </div>
                <div class="mt-4 flex items-baseline space-x-2">
                    <span id="bat-soc" class="text-3xl font-extrabold text-emerald-400">86</span>
                    <span class="text-sm font-semibold text-slate-400">% SOC</span>
                </div>
                <div class="w-full bg-slate-800 rounded-full h-2 mt-2 overflow-hidden">
                    <div id="bat-bar" class="bg-gradient-to-r from-emerald-500 to-teal-400 h-2 rounded-full transition-all duration-500" style="width: 86%"></div>
                </div>
                <p class="text-xs text-slate-500 mt-2 flex items-center justify-between">
                    <span>Volt: <strong id="bat-v" class="text-slate-300 font-mono">52.8 V</strong></span>
                    <span>Current: <strong id="bat-a" class="text-slate-300 font-mono">+16.4 A</strong></span>
                </p>
            </div>

            <!-- Card 4: Facility Load -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-slate-700">
                <div class="flex justify-between items-start">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Household Load</span>
                    <span id="load-badge" class="px-2 py-0.5 rounded text-xs font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30">NORMAL</span>
                </div>
                <div class="mt-4 flex items-baseline space-x-2">
                    <span id="load-w" class="text-3xl font-extrabold text-sky-400">680</span>
                    <span class="text-sm font-semibold text-slate-400">Watts</span>
                </div>
                <p class="text-xs text-slate-500 mt-2 flex items-center gap-1.5">
                    <i data-lucide="thermometer" class="w-3.5 h-3.5"></i>
                    Inverter Temp: <span id="temp-c" class="text-slate-300 font-mono">38.2°C</span>
                </p>
                <div class="absolute -right-2 -bottom-2 opacity-5 pointer-events-none">
                    <i data-lucide="home" class="w-24 h-24 text-sky-400"></i>
                </div>
            </div>

        </div>

        <!-- Middle Section: Power Flow Diagram & Generator Economics -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <!-- Power Flow Diagram (2 Cols) -->
            <div class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-base font-bold text-white flex items-center gap-2">
                        <i data-lucide="git-commit" class="w-5 h-5 text-emerald-400"></i>
                        Real-Time Inverter Energy Flow
                    </h2>
                    <span class="text-xs text-slate-400 font-mono">Sampling: 5,000ms • Modbus RTU</span>
                </div>

                <!-- Animated Diagram Node Box -->
                <div class="bg-slate-950/60 rounded-xl p-6 border border-slate-800/80 relative">
                    <div class="grid grid-cols-3 items-center text-center gap-4">
                        
                        <!-- Node: Solar Panels -->
                        <div class="p-4 rounded-xl bg-slate-900 border border-amber-500/30 flex flex-col items-center">
                            <i data-lucide="sun" class="w-8 h-8 text-amber-400 mb-1"></i>
                            <span class="text-xs text-slate-400 font-semibold uppercase">Solar Panels</span>
                            <span id="flow-pv-w" class="text-lg font-bold text-amber-300 mt-1">2,650 W</span>
                            <span class="text-[10px] text-emerald-400 flex items-center gap-0.5 mt-0.5">
                                <i data-lucide="arrow-down" class="w-3 h-3"></i> Inverter Feed
                            </span>
                        </div>

                        <!-- Central Inverter Hub -->
                        <div class="p-5 rounded-2xl bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-emerald-500/50 shadow-lg shadow-emerald-500/10 flex flex-col items-center">
                            <div class="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-2">
                                <i data-lucide="cpu" class="w-6 h-6 text-emerald-400"></i>
                            </div>
                            <span class="text-xs text-white font-bold">HYBRID INVERTER</span>
                            <span class="text-[10px] text-slate-400">Growatt SPF 5000 ES</span>
                            <div class="mt-2 text-xs font-mono px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                                48V DC • 230V AC
                            </div>
                        </div>

                        <!-- Node: Household Load -->
                        <div class="p-4 rounded-xl bg-slate-900 border border-sky-500/30 flex flex-col items-center">
                            <i data-lucide="home" class="w-8 h-8 text-sky-400 mb-1"></i>
                            <span class="text-xs text-slate-400 font-semibold uppercase">Facility Load</span>
                            <span id="flow-load-w" class="text-lg font-bold text-sky-300 mt-1">680 W</span>
                            <span class="text-[10px] text-sky-400 flex items-center gap-0.5 mt-0.5">
                                <i data-lucide="zap" class="w-3 h-3"></i> AC Output
                            </span>
                        </div>

                    </div>

                    <!-- Lower Nodes (Grid & Battery) -->
                    <div class="grid grid-cols-2 items-center text-center gap-6 mt-6">
                        
                        <!-- Grid Node -->
                        <div id="flow-grid-box" class="p-4 rounded-xl bg-slate-900 border border-emerald-500/30 flex items-center space-x-4">
                            <div class="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                                <i data-lucide="utility-pole" class="w-6 h-6 text-emerald-400"></i>
                            </div>
                            <div class="text-left">
                                <span class="text-xs text-slate-400 uppercase font-semibold">NEPA / Grid Bypass</span>
                                <div id="flow-grid-text" class="text-sm font-bold text-emerald-400">Online (226.4V)</div>
                            </div>
                        </div>

                        <!-- Battery Node -->
                        <div class="p-4 rounded-xl bg-slate-900 border border-teal-500/30 flex items-center space-x-4">
                            <div class="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center shrink-0">
                                <i data-lucide="battery-charging" class="w-6 h-6 text-teal-400"></i>
                            </div>
                            <div class="text-left flex-1">
                                <div class="flex justify-between items-center">
                                    <span class="text-xs text-slate-400 uppercase font-semibold">LiFePO4 Bank</span>
                                    <span id="flow-bat-soc" class="text-xs font-bold text-teal-400">86%</span>
                                </div>
                                <div id="flow-bat-text" class="text-xs font-mono text-slate-300">Charging (+16.4A)</div>
                            </div>
                        </div>

                    </div>
                </div>

                <!-- Simulation Event Trigger Buttons -->
                <div class="mt-4 pt-4 border-t border-slate-800">
                    <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2.5">
                        Test Nigerian Power Scenarios (Live Edge Simulation Controls):
                    </span>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="triggerScenario('toggle_grid')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="power" class="w-3.5 h-3.5 text-amber-400"></i> Toggle NEPA Outage
                        </button>
                        <button onclick="triggerScenario('heavy_load')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="zap-off" class="w-3.5 h-3.5 text-red-400"></i> Inject 2,750W Heavy Load
                        </button>
                        <button onclick="triggerScenario('normal_load')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i> Normal Load (650W)
                        </button>
                        <button onclick="triggerScenario('cloud_drop')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="cloud" class="w-3.5 h-3.5 text-slate-400"></i> Heavy Cloud Cover
                        </button>
                        <button onclick="triggerScenario('low_battery')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="battery-warning" class="w-3.5 h-3.5 text-orange-400"></i> Force Low SOC (32%)
                        </button>
                        <button onclick="triggerScenario('toggle_wifi')" class="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5">
                            <i data-lucide="wifi-off" class="w-3.5 h-3.5 text-sky-400"></i> Toggle Wi-Fi Drop
                        </button>
                    </div>
                </div>

            </div>

            <!-- Nigerian Generator Economics & Depletion Card -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between space-y-4">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center gap-2 mb-1">
                        <i data-lucide="fuel" class="w-5 h-5 text-amber-400"></i>
                        Generator Fuel Displacement
                    </h2>
                    <p class="text-xs text-slate-400">Economic calculation based on ₦1,150/L petrol benchmark</p>

                    <!-- Fuel Metrics -->
                    <div class="mt-4 space-y-3">
                        <div class="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
                            <span class="text-xs text-slate-400">Today's Fuel Displaced:</span>
                            <div class="flex items-baseline justify-between mt-1">
                                <span id="fuel-liters" class="text-2xl font-bold text-white">6.5</span>
                                <span class="text-xs font-semibold text-amber-400">Liters of Petrol</span>
                            </div>
                        </div>

                        <div class="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-900/40">
                            <span class="text-xs text-emerald-400">Today's Money Saved (₦):</span>
                            <div class="flex items-baseline justify-between mt-1">
                                <span id="money-naira" class="text-2xl font-extrabold text-emerald-300">₦7,475.00</span>
                                <span class="text-[10px] text-emerald-500 font-mono">0.35 L/kWh</span>
                            </div>
                        </div>

                        <div class="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
                            <span class="text-xs text-slate-400">Battery Runtime to Cutoff:</span>
                            <div class="flex items-baseline justify-between mt-1">
                                <span id="depletion-human" class="text-xl font-bold text-sky-300">Infinite</span>
                                <span class="text-[10px] text-slate-400 font-mono">Cutoff: 10% SOC</span>
                            </div>
                        </div>

                        <div class="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800">
                            <span class="text-xs text-slate-400">Offline Flash Buffer (LittleFS):</span>
                            <div class="flex items-baseline justify-between mt-1">
                                <span id="buffer-count" class="text-lg font-bold text-slate-200">0 / 1,500</span>
                                <span class="text-[10px] text-emerald-400 font-mono">2-Hour Retention</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40 text-[11px] text-slate-400">
                    💡 <em>Formula:</em> 1 kWh generated ≈ 0.35L fuel saved × ₦1,150/L. Estimated monthly household ROI is ~₦224,000.
                </div>
            </div>

        </div>

        <!-- Bottom Section: Live Telemetry Stream Terminal & WhatsApp Interactive Simulator -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <!-- Live Edge Modbus & MQTT Log Stream -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col h-[460px]">
                <div class="flex items-center justify-between mb-3">
                    <h2 class="text-sm font-bold text-white flex items-center gap-2">
                        <i data-lucide="terminal" class="w-4 h-4 text-emerald-400"></i>
                        Edge Modbus RTU / MQTT Telemetry Stream
                    </h2>
                    <span class="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/60">LIVE 5s</span>
                </div>
                <div id="log-terminal" class="flex-1 bg-slate-950 rounded-xl p-4 font-mono text-xs overflow-y-auto space-y-2 border border-slate-800/80 custom-scrollbar">
                    <div class="text-slate-500">// Waiting for telemetry stream from ESP32 edge gateway...</div>
                </div>
            </div>

            <!-- WhatsApp Interactive Chat Simulator -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col h-[460px]">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center space-x-2">
                        <div class="w-7 h-7 rounded-full bg-emerald-600 flex items-center justify-center text-white">
                            <i data-lucide="message-square" class="w-4 h-4"></i>
                        </div>
                        <div>
                            <h2 class="text-sm font-bold text-white">Solary WhatsApp Assistant</h2>
                            <p class="text-[10px] text-emerald-400">● Online (+234 803 123 4567)</p>
                        </div>
                    </div>
                    <span class="text-[10px] text-slate-400 font-mono">HMAC-SHA256</span>
                </div>

                <!-- Chat Messages Body -->
                <div id="chat-messages" class="flex-1 bg-slate-950 rounded-xl p-4 overflow-y-auto space-y-3 border border-slate-800/80 text-xs custom-scrollbar">
                    <!-- Populated dynamically -->
                </div>

                <!-- Chat Input & Quick Actions -->
                <div class="mt-3 space-y-2">
                    <div class="flex gap-1.5">
                        <button onclick="sendQuickReply('Status')" class="text-[11px] px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">⚡ Status</button>
                        <button onclick="sendQuickReply('Health')" class="text-[11px] px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">🩺 Health</button>
                        <button onclick="sendQuickReply('Savings')" class="text-[11px] px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">💰 Savings</button>
                    </div>
                    <form onsubmit="handleChatSubmit(event)" class="flex gap-2">
                        <input id="chat-input" type="text" placeholder="Type 'Status', 'Health', 'Savings'..." class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500">
                        <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl px-4 py-2 text-xs font-semibold flex items-center gap-1">
                            Send <i data-lucide="send" class="w-3 h-3"></i>
                        </button>
                    </form>
                </div>
            </div>

        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500">
        Solary Energy Intelligence & WhatsApp Alerting Platform • ESP32 FreeRTOS Edge • EMQX • TimescaleDB • Redis • Meta Cloud API
    </footer>

    <!-- Client-Side Real-Time Streaming Script -->
    <script>
        lucide.createIcons();

        // Connect Server-Sent Events (SSE) Stream
        const evtSource = new EventSource('/api/v1/live/stream');

        evtSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            } catch (err) {
                console.error("Failed to parse SSE payload", err);
            }
        };

        evtSource.onerror = function(err) {
            console.warn("SSE connection interrupted. Reconnecting automatically...", err);
        };

        function updateDashboard(data) {
            const tel = data.telemetry;
            const dep = data.depletion;
            const sav = data.savings;

            // Server Time
            document.getElementById('server-time').innerText = data.server_time;

            // Grid Status
            const gridStatusBadge = document.getElementById('grid-status-badge');
            const gridV = document.getElementById('grid-v');
            const flowGridBox = document.getElementById('flow-grid-box');
            const flowGridText = document.getElementById('flow-grid-text');

            gridV.innerText = tel.grid_v.toFixed(1);
            if (tel.grid_on) {
                gridStatusBadge.innerText = 'AVAILABLE';
                gridStatusBadge.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                flowGridBox.className = 'p-4 rounded-xl bg-slate-900 border border-emerald-500/30 flex items-center space-x-4';
                flowGridText.innerText = 'Online (' + tel.grid_v.toFixed(1) + 'V)';
                flowGridText.className = 'text-sm font-bold text-emerald-400';
            } else {
                gridStatusBadge.innerText = 'NEPA DOWN';
                gridStatusBadge.className = 'px-2 py-0.5 rounded text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/30';
                flowGridBox.className = 'p-4 rounded-xl bg-slate-900 border border-red-500/30 flex items-center space-x-4';
                flowGridText.innerText = 'Outage (0.0V)';
                flowGridText.className = 'text-sm font-bold text-red-400';
            }

            // Solar PV
            document.getElementById('pv-w').innerText = tel.pv_w.toLocaleString();
            document.getElementById('pv-v').innerText = tel.pv_v.toFixed(1) + ' V';
            document.getElementById('flow-pv-w').innerText = tel.pv_w.toLocaleString() + ' W';

            // Battery
            document.getElementById('bat-soc').innerText = tel.bat_soc;
            document.getElementById('bat-bar').style.width = tel.bat_soc + '%';
            document.getElementById('bat-v').innerText = tel.bat_v.toFixed(1) + ' V';
            document.getElementById('bat-a').innerText = (tel.bat_a >= 0 ? '+' : '') + tel.bat_a.toFixed(1) + ' A';
            document.getElementById('flow-bat-soc').innerText = tel.bat_soc + '%';

            const batModeBadge = document.getElementById('bat-mode-badge');
            const flowBatText = document.getElementById('flow-bat-text');
            if (tel.bat_a > 1.0) {
                batModeBadge.innerText = '⚡ CHARGING';
                batModeBadge.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
                flowBatText.innerText = 'Charging (+' + tel.bat_a.toFixed(1) + 'A)';
                flowBatText.className = 'text-xs font-mono text-emerald-400';
            } else if (tel.bat_a < -1.0) {
                batModeBadge.innerText = '🔋 DISCHARGING';
                batModeBadge.className = 'px-2 py-0.5 rounded text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30';
                flowBatText.innerText = 'Discharging (' + tel.bat_a.toFixed(1) + 'A)';
                flowBatText.className = 'text-xs font-mono text-orange-400';
            } else {
                batModeBadge.innerText = 'IDLE';
                batModeBadge.className = 'px-2 py-0.5 rounded text-xs font-bold bg-slate-500/20 text-slate-400 border border-slate-500/30';
                flowBatText.innerText = 'Float / Standby';
                flowBatText.className = 'text-xs font-mono text-slate-400';
            }

            // Load
            document.getElementById('load-w').innerText = tel.load_w.toLocaleString();
            document.getElementById('flow-load-w').innerText = tel.load_w.toLocaleString() + ' W';
            document.getElementById('temp-c').innerText = tel.temp_c.toFixed(1) + '°C';

            // Depletion & Critical Alert
            const alertBox = document.getElementById('critical-alert-box');
            const alertDepletionTime = document.getElementById('alert-depletion-time');
            document.getElementById('depletion-human').innerText = dep.human;

            if (dep.is_critical) {
                alertBox.classList.remove('hidden');
                alertDepletionTime.innerText = dep.human;
            } else {
                alertBox.classList.add('hidden');
            }

            // Savings
            document.getElementById('fuel-liters').innerText = sav.fuel_liters_displaced.toFixed(1);
            document.getElementById('money-naira').innerText = '₦' + sav.money_saved_naira.toLocaleString('en-US', {minimumFractionDigits: 2});

            // Wi-Fi & Buffer
            const wifiBadge = document.getElementById('wifi-badge');
            const wifiText = document.getElementById('wifi-status-text');
            const bufferCount = document.getElementById('buffer-count');

            if (tel.wifi_connected) {
                wifiBadge.className = 'flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-400';
                wifiText.innerText = 'Wi-Fi Online';
            } else {
                wifiBadge.className = 'flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-amber-950/60 border border-amber-800 text-amber-400 animate-pulse';
                wifiText.innerText = 'Cellular Fallback (Buffering Flash)';
            }
            bufferCount.innerText = tel.buffered_count + ' / 1,500';

            // Append Log Terminal Entry
            appendTerminalLog(tel);

            // Sync Chat History
            renderChatHistory(data.chat_history);
        }

        let lastLogTimestamp = 0;
        function appendTerminalLog(tel) {
            if (tel.timestamp === lastLogTimestamp) return;
            lastLogTimestamp = tel.timestamp;

            const terminal = document.getElementById('log-terminal');
            const div = document.createElement('div');
            div.className = 'text-[11px] leading-relaxed border-b border-slate-900 pb-1';
            
            const timeStr = new Date(tel.timestamp * 1000).toLocaleTimeString();
            div.innerHTML = `<span class="text-slate-500">[${timeStr}]</span> ` +
                `<span class="text-emerald-400">MQTT PUB</span> ` +
                `<span class="text-slate-400">devices/${tel.device_id}/telemetry:</span> ` +
                `<span class="text-amber-300">{"grid_v": ${tel.grid_v}, "grid_on": ${tel.grid_on}, "pv_w": ${tel.pv_w}, "bat_soc": ${tel.bat_soc}, "load_w": ${tel.load_w}}</span>`;
            
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;

            // Keep terminal lean
            while (terminal.children.length > 25) {
                terminal.removeChild(terminal.children[0]);
            }
        }

        function renderChatHistory(chat) {
            if (!chat) return;
            const container = document.getElementById('chat-messages');
            container.innerHTML = '';

            chat.forEach(msg => {
                const isUser = (msg.sender === 'user');
                const bubble = document.createElement('div');
                bubble.className = isUser ? 'flex justify-end' : 'flex justify-start';

                const formattedText = msg.text
                    .replace(/\\n/g, '<br>')
                    .replace(/\\*(.*?)\\*/g, '<strong>$1</strong>')
                    .replace(/_(.*?)_/g, '<em>$1</em>');

                bubble.innerHTML = `
                    <div class="max-w-[85%] rounded-2xl px-3.5 py-2.5 ${isUser ? 'bg-emerald-700 text-white rounded-br-none' : 'bg-slate-800 text-slate-100 border border-slate-700 rounded-bl-none'}">
                        <div class="leading-relaxed">${formattedText}</div>
                        <div class="text-[9px] text-right mt-1 opacity-70">${msg.time}</div>
                    </div>
                `;
                container.appendChild(bubble);
            });
            container.scrollTop = container.scrollHeight;
        }

        async function triggerScenario(name) {
            try {
                const res = await fetch('/api/v1/live/scenario', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({scenario: name})
                });
                const data = await res.json();
                console.log("Scenario applied:", data);
            } catch (err) {
                console.error("Error triggering scenario:", err);
            }
        }

        async function sendQuickReply(text) {
            document.getElementById('chat-input').value = text;
            handleChatSubmit(new Event('submit'));
        }

        async function handleChatSubmit(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('chat-input');
            const text = input.value.trim();
            if (!text) return;
            input.value = '';

            try {
                await fetch('/api/v1/live/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });
            } catch (err) {
                console.error("Chat send failed", err);
            }
        }
    </script>
</body>
</html>
"""
