import os
import time
import hashlib
import logging

import redis
import psycopg2
from flask import Flask,request,jsonify,redirect

from prometheus_client import (
    Counter,Histogram,Gauge,
    generate_latest,CONTENT_TYPE_LATEST
)
import redis.exceptions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s, %(name)s %(message)s'
    
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


#prometheus metrics

REQUESTS_TOTAL = Counter(
    'shorturl_requests_total',
    'Total HTTP requests received',
    ['endpoint','method','status_code']
)

REQUEST_DURATION = Histogram(
    'shorturl_request_duration_seconds',
    'HTTP request duration in seconds',
    ['endpoint'],
    buckets=[0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0,2.5]
)

CACHE_HITS=Counter(
    'shorturl_cache_hists_total',
    'Redis cache hits and misses',
    ['result']
)

ACTIVE_URLS = Gauge(
    'shorturl_active_urls_total',
    'Total active shortened URLs in the distance'
    
)

from psycopg2 import pool

db_pool = pool.ThreadedConnectionPool(
    minconn=2,maxconn=20,
    host=os.environ.get('DB_HOST','localhost'),
    port=os.environ.get('DB_PORT',5432),
    database=os.environ.get('DB_NAME','urldb'),
    user=os.environ.get('DB_USER','urluser'),
    password=os.environ.get('DB_PASSWORD','urlpass')
)

def get_Db_conn():
    return db_pool.getconn()

def release_db_conn(conn):
    db_pool.putconn(conn)

POOL_AVALIABLE = Gauge('shorturl_db_pool_available_connections','Number of available connections in the DB pool')   
   
   
def update_db_pool_metrics():
    POOL_AVALIABLE.set(len(db_pool._pool)) 
    
"""def get_db():
    """"Create a fresh PostgresSQL connection.""""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        port=os.environ.get('DB_PORT',5432),
        database=os.environ.get('DB_NAME','urldb'),
        user=os.environ.get('DB_USER','urluser'),
        password=os.environ.get('DB_PASSWORD','urlpass')
        
    )"""
    
def get_cache():
    """Create a fresh Redis connection."""
    return redis.Redis(
        host=os.environ.get('REDIS_HOST','localhost'),
        port=int(os.environ.get('REDIS_PORT',6379)),
        decode_responses=True
        
    )
    

def init_db():
    """Create the urls table id it doesn't exists."""
    
    conn=get_Db_conn()
    cur=conn.cursor()
    cur.execute('''
                CREATE TABLE IF NOT EXISTS urls(
                    id         SERIAL PRIMARY KEY,
                    code       VARCHAR(10) UNIQUE NOT NULL,
                    long_url   TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    hit_count  INTEGER DEFAULT 0       
                )
                ''')
    conn.commit()
    cur.close()
    release_db_conn(conn)
    logger.info("Database initialised successfully")
    
    

def make_short_code(long_url: str) -> str:
    return hashlib.md5(long_url.encode()).hexdigest()[:7]



@app.route('/shorten',methods=['POST'])
def shorten():
    start_time=time.time() #starts the stopwatch
    
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            REQUESTS_TOTAL.labels(
                endpoint='/shorten',method='POST',status_code='400'
            ).inc()
            return jsonify({'error':'url field is required'}),400
        
        long_url = data['url'].strip()
        if not long_url.startswith(('http://','https://')):
            REQUESTS_TOTAL.labels(
                endpoint='/shorten',method='POST',status_code='400'
            ).inc()
            return jsonify({'error':'url must start with http:// or https://'}),400
        
        short_code = make_short_code(long_url)
        
        conn=get_Db_conn()
        cur=conn.cursor()
        cur.execute(
            '''INSERT INTO urls (code,long_url)
               VALUES (%s,%s)
              ON CONFLICT (code) DO NOTHING''',
              (short_code,long_url)
        )
        conn.commit()
        cur.close
        release_db_conn(conn)        
        _update_url_count()
        
        REQUESTS_TOTAL.labels(
            endpoint='/shorten',method='POST',status_code ='201'
        ).inc()
        
        logger.info("Shortend URL : %s -> %s",long_url[:50],short_code)
        return jsonify({'short_code': short_code,'short_url':f'/r/{short_code}'}),201
    
    except Exception as e:
        logger.error("Error in /shorten: %s" ,e)
        REQUESTS_TOTAL.labels(
            endpoint='/shorten', method='POST',status_code='500'
        ).inc()
        return jsonify({'error:' 'internal server error'}),500
    
    finally:
        
        duration=time.time() - start_time
        REQUEST_DURATION.labels(endpoint='/shorten').observe(duration)
        
        
        
        
#endpoint 2 GET /r/<code>

@app.route('/r/<code>',methods=['GET'])
def redirect_url(code):
    start_time=time.time()
    
    try:
        cache = get_cache()
        
        #check redis cache first -- much faster than postgresql
        cached_url = cache.get(f'url:{code}')
        
        if cached_url:
            
            CACHE_HITS.labels(result='hit').inc()
            REQUESTS_TOTAL.labels(
                endpoint='/r',method='GET',status_code='302'
            ).inc()
            logger.info("cache HIT for code: %s",code)
            return redirect(cached_url,code=302)
        
        CACHE_HITS.labels(result='miss').inc()
        
        conn=get_Db_conn()
        cur=conn.cursor()
        cur.execute(
            'SELECT long_url FROM urls WHERE code = %s', (code,)
        )
        row=cur.fetchone()
        
        if not row:
            cur.close()
            release_db_conn(conn)
            REQUESTS_TOTAL.labels(
                endpoint='/r',method='GET',status_code='404'
            ).inc()
            return jsonify({'error':'short code not found'}),404
        
        long_url = row[0]
        
        cur.execute(
            'UPDATE urls SET hit_count = hit_count + 1 WHERE code = %s',(code,)
        )
        conn.commit()
        cur.close()
        release_db_conn(conn)        
        cache.setex(f'url:{code}',3600,long_url)
        
        REQUESTS_TOTAL.labels(
            endpoint='/r',method='GET',status_code='302'
        ).inc()
        logger.info("Cache MISS for code: %s, fetched from DB",code)
        return redirect(long_url,code=302)
    
    
    except redis.exceptions.ConnectionError:
        
        logger.warning("Redis unavaiable ,falling back to DB only")
        CACHE_HITS.labels(result='miss').inc()
        
        try:
            conn=get_Db_conn()
            cur= conn.cursor()
            cur.execute('SELECT long_url FROM urls WHERE code = %s', (code,))
            row=cur.fetchone()
            cur.close()
            release_db_conn(conn)            
            if not row:
                REQUESTS_TOTAL.labels(
                    endpoint='/r',method='GET',status_code='404'
                ).inc()
                return jsonify({'error':'short code not found'}),404
            
            REQUESTS_TOTAL.labels(
                endpoint='/r',method='GET',status_code='302'
            ).inc()
            return redirect(row[0],code=302)
        
        except Exception as e:
            logger.error("DB also failed : %s",e)
            REQUESTS_TOTAL.labels(
                endpoint='/r',method='GET',status_code='500'
            ).inc()
            return jsonify({'error':'service unavaiable'}),500
        
        except Exception as e:
            logger.error("Error in /r/%s: %s",code,e)
            REQUESTS_TOTAL.labels(
                endpoint='/r',method='GET',status_code='500'
            )
            
        finally:
            duration = time.time() - start_time
            REQUEST_DURATION.labels(endpoint='/r').observe(duration)
            

#endpoint 3
@app.route('/metrics')
def metrics():
    return generate_latest(),200,{'Content-Type':CONTENT_TYPE_LATEST}
        
        

@app.route('/health')
def health():
    status = {'status':'ok','checks':{}}
    
    try:
        conn=get_Db_conn()
        release_db_conn(conn)
        status['checks']['database']='ok'
        
    except Exception as e:
        status['checks']['database'] = f'error:{e}'
        status['status']='degraded'
        
    
    try:
        cache=get_cache()
        cache.ping()
        status['checks']['redis']='ok'
    except Exception:
        status['checks']['redis']='unavaiable'
        
    
    http_status = 200 if status['status'] == 'ok' else 207
    return jsonify(status),http_status



def _update_url_count():
    try:
        conn=get_Db_conn()
        cur=conn.cursor()
        cur.execute('SELECT COUNT(*) FROM urls')
        count = cur.fetchone()[0]
        cur.close()
        release_db_conn(conn)
        ACTIVE_URLS.set(count)
    except Exception as e:
        logger.warning("Could not update URL count gauge: %s",e)
        
 
import json, logging, sys

class JSONFormatter(logging.Formatter):
    def format(self,record):
        log_obj={
            "timestamp":self.formatTime(record),
            "level":record.levelname,
            "message":record.getMessage(),
            "module":record.module,
        }
        if hasattr(record,'request_id'):
            log_obj['request_id']=record.request_id
        return json.dumps(log_obj)
    
handler=logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger=logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

 
        
if __name__  == '__main__':
    logger.info("Starting URL Shortner API ...")
    init_db()
    app.run(host='0.0.0.0',port=5000,debug=False)
    

