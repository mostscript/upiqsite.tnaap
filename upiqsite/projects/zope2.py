
def initialize(context):
    """called to make this a Zope 2 product package"""
    patch_access_logging()


def patch_access_logging():
    """
    Monkey patch access logging with a wrapper that returns
    before emitting any messages for OPTIONS requests from haproxy
    health checks.
    """
    from ZServer.AccessLogger import AccessLogger
    _orig = AccessLogger.log

    def newlog(self, message):
        if 'OPTIONS / HTTP/1.0' in message:
            return  # do not emit log message for haproxy health check
        _orig(self, message)

    setattr(AccessLogger, 'log', newlog)

