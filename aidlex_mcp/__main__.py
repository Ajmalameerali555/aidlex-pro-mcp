import os
import uvicorn

def main():
    # One process is sufficient for this synchronous SQLAlchemy-backed deployment.
    # HTTP call concurrency is async; model requests have a separate bound.
    uvicorn.run('aidlex_mcp.app:create_app',factory=True,host='0.0.0.0',port=int(os.environ.get('PORT','8000')),access_log=False,proxy_headers=False)

if __name__=='__main__': main()
