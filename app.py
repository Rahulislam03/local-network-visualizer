from flask import Flask, render_template, jsonify
from scapy.all import ARP, Ether, srp

app = Flask(__name__)

def scan_network(ip_range):
    # ARP প্রোটোকল দিয়ে ডিভাইসের IP ও MAC খোঁজা
    arp = ARP(pdst=ip_range)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp

    # প্যাকেট পাঠানো ও রেসপন্স সংগ্রহ
    result = srp(packet, timeout=2, verbose=0)[0]

    devices = []
    for sent, received in result:
        devices.append({'ip': received.psrc, 'mac': received.hwsrc})
    
    return devices

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/network-data')
def get_network_data():
    # রাউটারের সাবনেট অনুযায়ী IP রেঞ্জ দিন (প্রয়োজনে 192.168.1.1/24 করতে পারেন)
    devices = scan_network('192.168.0.1/24') 
    
    nodes = [{'id': 'router', 'label': 'Gateway Router', 'group': 'router'}]
    edges = []

    for idx, dev in enumerate(devices):
        node_id = f"dev_{idx}"
        nodes.append({
            'id': node_id,
            'label': f"IP: {dev['ip']}\nMAC: {dev['mac']}",
            'group': 'device'
        })
        edges.append({'from': 'router', 'to': node_id})

    return jsonify({'nodes': nodes, 'edges': edges})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
