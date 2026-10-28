#!/usr/bin/env python3
import sys
import time
import os
import urllib.request
import json

API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1/live/status")

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[38;5;48m"
RED = "\033[38;5;196m"
YELLOW = "\033[38;5;220m"
BLUE = "\033[38;5;75m"
CYAN = "\033[38;5;51m"
MAGENTA = "\033[38;5;207m"
GRAY = "\033[38;5;244m"
BG_DARK = "\033[48;5;234m"

def draw_bar(percent, width=24, color=GREEN):
    filled = int(round((percent / 100.0) * width))
    empty = width - filled
    return f"{color}{'█' * filled}{GRAY}{'░' * empty}{RESET} {BOLD}{percent}%{RESET}"

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def main():
    clear_screen()
    print(f"{YELLOW}Connecting to Solary Energy Intelligence live feed at {API_URL}...{RESET}")

    while True:
        try:
            req = urllib.request.Request(API_URL, headers={"User-Agent": "TerminalMonitor/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tel = data["telemetry"]
            dep = data["depletion"]
            sav = data["savings"]
            alerts = data.get("alerts", [])

            grid_badge = f"{GREEN}[ ⚡ GRID AVAILABLE - {tel['grid_v']:.1f}V ]{RESET}" if tel["grid_on"] else f"{RED}[ 🔌 NEPA OUTAGE - 0.0V ]{RESET}"
            
            bat_color = GREEN if tel["bat_soc"] > 50 else (YELLOW if tel["bat_soc"] > 25 else RED)
            bat_mode = f"{GREEN}⚡ CHARGING (+{tel['bat_a']:.1f}A){RESET}" if tel["bat_a"] > 1.0 else (f"{RED}🔋 DISCHARGING ({tel['bat_a']:.1f}A){RESET}" if tel["bat_a"] < -1.0 else f"{GRAY}IDLE (0.0A){RESET}")

            # Render Screen
            clear_screen()
            print(f"{BOLD}{BG_DARK}========================================================================{RESET}")
            print(f"{BOLD}{YELLOW} ☀️  SOLARY — IOT SOLAR ENERGY INTELLIGENCE & ALERTING PLATFORM {RESET}")
            print(f"{GRAY} Site: Lekki Phase 1 Hybrid (Growatt SPF 5000 ES) • Edge ID: {tel['device_id']}{RESET}")
            print(f"{GRAY} Live Sampling: 5,000ms • Server Time: {data['server_time']}{RESET}")
            print(f"{BOLD}{BG_DARK}========================================================================{RESET}\n")

            # Grid & Solar
            print(f"{BOLD}1. INVERTER INPUTS:{RESET}")
            print(f"   AC Grid Status   : {grid_badge}")
            print(f"   Solar PV Power   : {YELLOW}{BOLD}{tel['pv_w']:,} W{RESET}  ({tel['pv_v']:.1f} V DC)")
            print(f"   Inverter Temp    : {CYAN}{tel['temp_c']:.1f}°C{RESET}\n")

            # Battery Bank
            print(f"{BOLD}2. 48V BATTERY STORAGE (LiFePO4 10kWh):{RESET}")
            print(f"   State of Charge  : {draw_bar(tel['bat_soc'], 20, bat_color)}")
            print(f"   Battery Voltage  : {BOLD}{tel['bat_v']:.1f} V{RESET}")
            print(f"   Operating State  : {bat_mode}")
            print(f"   Runtime to Cutoff: {MAGENTA}{BOLD}{dep['human']}{RESET} (Cutoff: 10% SOC)\n")

            # Facility Load
            print(f"{BOLD}3. FACILITY CONSUMPTION & POWER BALANCE:{RESET}")
            print(f"   Current Load     : {BLUE}{BOLD}{tel['load_w']:,} W{RESET}")
            net = tel['pv_w'] - tel['load_w']
            net_str = f"{GREEN}+{net:,} W (Surplus to Battery){RESET}" if net >= 0 else f"{RED}{net:,} W (Deficit from Battery){RESET}"
            print(f"   Solar Net Balance: {net_str}\n")

            # Generator Fuel ROI
            print(f"{BOLD}4. PETROL GENERATOR REPLACEMENT ECONOMICS (₦1,150/L):{RESET}")
            print(f"   Fuel Displaced   : {YELLOW}{sav['fuel_liters_displaced']:.2f} Liters{RESET} today")
            print(f"   Daily Money Saved: {GREEN}{BOLD}₦{sav['money_saved_naira']:,.2f}{RESET}")
            print(f"   Offline Buffer   : {tel['buffered_count']} / 1,500 records ({'Cellular' if not tel['wifi_connected'] else 'Wi-Fi'})\n")

            # Active Alerts
            if dep["is_critical"]:
                print(f"{RED}{BOLD}🚨 CRITICAL ALERT ACTIVE: High load ({tel['load_w']}W) on battery backup! Depletion in {dep['human']}!{RESET}")
            elif alerts:
                last_alert = alerts[-1]
                print(f"{CYAN}Latest Notification [{last_alert['time']}]: {last_alert['type']}{RESET}")

            print(f"\n{GRAY}Tip: Open http://localhost:8000/dashboard in your browser for graphical live UI.{RESET}")
            print(f"{GRAY}Press Ctrl+C to exit monitor.{RESET}")

        except Exception as e:
            clear_screen()
            print(f"{RED}Waiting for Solar Intelligence server... ({e}){RESET}")
            print(f"{GRAY}Start server via: uvicorn app.main:app --port 8000{RESET}")

        time.sleep(1.5)

if __name__ == "__main__":
    main()
