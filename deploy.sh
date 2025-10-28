#!/bin/bash
cd /root/stream-bot-manager
echo "Deploying server..."
cd server
npm install
pm2 restart stream-server || pm2 start server.js --name stream-server
cd ../bot
pip3 install -r requirements.txt
pm2 restart stream-bot || pm2 start bot.py --interpreter python3 --name stream-bot
pm2 save
pm2 status
