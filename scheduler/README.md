# Scheduler
Will build out example.  However, for now, to test token exchange:

```sh
# populate .env with environment variables below
export $(xargs < .env)

# Token exchange to get refresh_token and store
curl -i -X POST "$SCHED_ISSUER/oauth/v2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$SCHED_CLIENT_ID" \
  -d "client_secret=$SCHED_CLIENT_SECRET" \
  -d "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
  -d "subject_token=$SCHED_SUBJECT_TOKEN" \
  -d "subject_token_type=urn:ietf:params:oauth:token-type:access_token" \
  -d "requested_token_type=urn:ietf:params:oauth:token-type:access_token"

# Extract refresh_token, place in SCHED_REFRESH_TOKEN in .env

# Later use refresh token to get JWT
curl -i -X POST "$SCHED_ISSUER/oauth/v2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$SCHED_CLIENT_ID" \
  -d "client_secret=$SCHED_CLIENT_SECRET" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$SCHED_REFRESH_TOKEN"
```


# Run Local 
```sh
uvicorn main:app --host 0.0.0.0 --port 8000
```

# Build
```sh
docker build -t fastapi-scheduler:0.1.0 .
```