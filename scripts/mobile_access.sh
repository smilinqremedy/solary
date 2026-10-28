#!/usr/bin/env bash
# =============================================================================
# Mobile Access Helper for Nigerian Solar Intelligence Platform
# =============================================================================

LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' | head -n 1)
PORT=8000

echo "========================================================================"
echo " ☀️ SOLARY — IOT ENERGY INTELLIGENCE MOBILE ACCESS"
echo "========================================================================"
echo ""
echo "📱 METHOD 1: SAME WI-FI / LOCAL NETWORK ACCESS"
echo "------------------------------------------------------------------------"
echo "If your mobile phone is connected to the same Wi-Fi router:"
echo ""
echo "👉 Open in your mobile browser:"
echo "   http://${LOCAL_IP}:${PORT}/dashboard"
echo ""
echo "------------------------------------------------------------------------"
echo "🌐 METHOD 2: CELLULAR DATA / ANYWHERE IN THE WORLD (PUBLIC HTTPS TUNNEL)"
echo "------------------------------------------------------------------------"
echo "If your phone is on mobile data (MTN / Airtel / Glo) or away from home,"
echo "start a secure Cloudflare tunnel by running:"
echo ""
echo "   /home/student/cloudflared tunnel --url http://localhost:${PORT}"
echo ""
echo "This will give you a free, public HTTPS link (e.g. https://xxx.trycloudflare.com)"
echo "that can be opened from ANY smartphone globally."
echo ""
echo "------------------------------------------------------------------------"
echo "💬 METHOD 3: META WHATSAPP ON YOUR MOBILE PHONE"
echo "------------------------------------------------------------------------"
echo "You can interact directly via WhatsApp without opening any web browser:"
echo "   - Send 'Status'  to get live Grid, Solar, Battery & Load."
echo "   - Send 'Savings' to see today's generator petrol liters & Naira saved."
echo "   - Send 'Health'  for battery cell sag and cycle diagnostics."
echo "========================================================================"
