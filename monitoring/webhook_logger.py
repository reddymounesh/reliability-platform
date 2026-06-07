import json
import logging
from datetime import datetime
from flask import Flask,request,jsonify

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger=logging.getLogger(__name__)
app=Flask(__name__)

def format_alert(data: dict) -> str:
    alerts=data.get('alerts',[])
    lines=[f"n{'='*60}",
           f" ALERTMANAGER WEBHOOK - {datetime.now().strftime('%H:%M:%S')}",
           f" Status: {data.get('status','unknown').upper()}",
           f"{'='*60}"]
    
    for a in alerts:
        labels=a.get('labels',{})
        ann=a.get('annotations',{})
        lines.append(f" [{labels.get('severity','?').upper()}] {labels.get('alertname','?')}")
        lines.append(f" Summary: {ann.get('Summary','no summary')}")
        lines.append("")
        
    return "\n".join(lines)

@app.route('/alert',methods=['POST'])
def receive_alert():
    data=request.get_json(force=True)
    print(format_alert(data),flush=True)
    return jsonify({'status': 'received'}),20

@app.route('/critical',methods=['POST'])
def receive_critcal():
    data=request.get_json(force=True)
    print(f"\n critical Alert {format_alert(data)}",flush=True)
    return jsonify({'status': 'received'}),200

@app.route('/health')
def health():
    return jsonify({'status':'ok'}),200


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5001)
    
    

