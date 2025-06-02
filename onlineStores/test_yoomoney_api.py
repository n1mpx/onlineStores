from yoomoney import Authorize

Authorize(
    client_id='2D2911059CE36FF631926D8E271C58858EAE979CE86B8632619CAAFAE99248FF',
    redirect_uri='http://site.ru',
    scope=[
        'account-info',
        'operation-history',
        'operation-details',
        'incoming-transfers',
        'payment-p2p',
        'payment-shop'
    ],
    client_secret='qwerty'
)