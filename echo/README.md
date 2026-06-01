# Echo

Run simple echo server behind Kong.

See [kong](../kong/README.md) for information on installing Kong.



## Echo Direct
Deploy a sample echo backend and route it through Kong.

`echo.yaml` defines the echo Deployment/Service, an `IngressClass` named `kong` (the class the controller is configured with via `CONTROLLER_INGRESS_CLASS=kong`), and an `Ingress` for host `echo.example.com`.

```sh
kubectl apply -f echo-direct.yaml
kubectl get pods -l app=echo-server   # wait for Running
```

Send traffic to the proxy (the `kong-gateway-proxy` LoadBalancer Service on
port 80):

```sh
curl -i http://localhost/ -H "Host: echo.example.com"
```

A `200` with the request echoed back as JSON confirms the ingress path works.


## Echo JWT


Convert JWK to PEM 

https://8gwifi.org/jwkconvertfunctions.jsp


Pull JWK
```json
{
      "use": "sig",
      "kty": "RSA",
      "kid": "373932351832523201",
      "alg": "RS256",
      "n": "q6n_lSKZQndYLorydQJ6xphPn2-mciQH7xxYSEWA1ru0is6fssVV169cWSXb5U0AZAE-URW3zZpfdpeaYBa_DYo1QusZopHHbXnlE-wGe5yPPDFCnca7Uol_PChA4YCtdqzWm679WBODYyFPSAouVToANoYVyFVc--SXqrF7swaltiph-EbSotA7zluLMzUarAT5552C0ZYiC5GyA0o7HSpWPrzaK-olc_BsytXcmyIDDsfgmiqwdEzaa5b7xDuKcsVMGkPn3d_GPx-mrggQ2vn8ZU0_10nDK0iBeqLSKwYy6AE2naZssKIyUCrOY22jmyqnxfnMXrHj0-cmBQ3MZw",
      "e": "AQAB"
    }
```

Use in secret

```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAq6n/lSKZQndYLorydQJ6
xphPn2+mciQH7xxYSEWA1ru0is6fssVV169cWSXb5U0AZAE+URW3zZpfdpeaYBa/
DYo1QusZopHHbXnlE+wGe5yPPDFCnca7Uol/PChA4YCtdqzWm679WBODYyFPSAou
VToANoYVyFVc++SXqrF7swaltiph+EbSotA7zluLMzUarAT5552C0ZYiC5GyA0o7
HSpWPrzaK+olc/BsytXcmyIDDsfgmiqwdEzaa5b7xDuKcsVMGkPn3d/GPx+mrggQ
2vn8ZU0/10nDK0iBeqLSKwYy6AE2naZssKIyUCrOY22jmyqnxfnMXrHj0+cmBQ3M
ZwIDAQAB
-----END PUBLIC KEY-----
```