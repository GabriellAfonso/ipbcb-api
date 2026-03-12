from uvicorn.workers import UvicornWorker


class IPBCBUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "root_path": "/ipbcb"}
