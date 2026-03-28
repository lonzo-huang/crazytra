"""
临时 Polymarket API 服务
提供 Polymarket 数据给前端，直到 Go API Gateway 实现
"""

from flask import Flask, jsonify
from flask_cors import CORS
import redis
import json

app = Flask(__name__)
CORS(app)  # 允许跨域

# 连接 Redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@app.route('/api/v1/polymarket/markets', methods=['GET'])
def get_markets():
    """获取 Polymarket 市场列表"""
    try:
        # 从 Redis 获取活跃市场列表
        market_ids = redis_client.zrevrange('polymarket:markets:active', 0, 19)
        
        if not market_ids:
            return jsonify([])
        
        # 获取每个市场的详细数据
        markets = []
        for market_id in market_ids:
            key = f'polymarket:market:{market_id}'
            data = redis_client.get(key)
            
            if data:
                try:
                    market = json.loads(data)
                    markets.append(market)
                except:
                    continue
        
        return jsonify(markets)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/polymarket/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        count = redis_client.get('polymarket:markets:count') or 0
        active_count = redis_client.zcard('polymarket:markets:active')
        
        return jsonify({
            'total_markets': count,
            'active_markets': active_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print("🚀 Starting Polymarket API server on http://localhost:8080")
    print("📡 Serving data from Redis")
    print("🌐 CORS enabled for frontend")
    app.run(host='0.0.0.0', port=8080, debug=True)
