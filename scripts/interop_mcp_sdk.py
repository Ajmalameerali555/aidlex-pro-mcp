#!/usr/bin/env python3
"""Optional independent official SDK client probe; install requirements-interop.txt."""
import argparse
import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def probe(url):
    token=os.environ.get('AIDLEX_TEST_ACCESS_TOKEN')
    headers={'Authorization':'Bearer '+token} if token else None
    async with streamablehttp_client(url,headers=headers) as (read,write,_):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            result=await session.call_tool('aidlex_server_status',{})
            if result.isError: raise RuntimeError('Status tool returned an error.')
            print('Official SDK initialization, tools/list and status call passed.')
            print('Discovered tools:',', '.join(t.name for t in tools.tools))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8000/mcp')
    asyncio.run(probe(parser.parse_args().url))
