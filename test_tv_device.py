import asyncio, httpx, uuid, json

CLIENT_ID = '861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com'
CLIENT_SECRET = 'SboVhoG9s0rNafixCSGGKXAT'
SCOPES = 'https://gdata.youtube.com https://www.googleapis.com/auth/youtube'

async def test():
    async with httpx.AsyncClient() as client:
        # 1. Get device code
        resp = await client.post(
            'https://www.youtube.com/o/oauth2/device/code',
            json={
                'client_id': CLIENT_ID,
                'scope': SCOPES,
                'device_id': uuid.uuid4().hex,
                'device_model': 'ytlr::'
            },
            headers={'Content-Type': 'application/json'}
        )
        data = resp.json()
        print("Go to", data['verification_url'])
        print("Enter code:", data['user_code'])
        
        # 2. Poll for token
        while True:
            await asyncio.sleep(data['interval'])
            resp = await client.post(
                'https://www.youtube.com/o/oauth2/token',
                json={
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'code': data['device_code'],
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
                },
                headers={'Content-Type': 'application/json'}
            )
            tdata = resp.json()
            if 'error' in tdata:
                if tdata['error'] == 'authorization_pending':
                    print("Waiting...")
                    continue
                else:
                    print("Error:", tdata)
                    break
            else:
                print("Got token!")
                access_token = tdata['access_token']
                
                # Test innertube
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                }
                data = {
                    'context': {
                        'client': {
                            'clientName': 'WEB',
                            'clientVersion': '2.20240101.00.00'
                        }
                    },
                    'videoId': 'q2HoLuVQg-s'
                }
                player_resp = await client.post(
                    'https://www.youtube.com/youtubei/v1/player',
                    headers=headers,
                    json=data
                )
                print("Player status:", player_resp.status_code)
                print(player_resp.text[:200])
                break

asyncio.run(test())
