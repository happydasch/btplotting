class BacktraderPlottingTab:

    def __init__(self, app, figurepage, client=None):
        self.app = app
        self.figurepage = figurepage
        self.client = client

    def is_useable(self):
        raise Exception("is_useable needs to be implemented.")

    def get_panel(self):
        raise Exception("get_panel needs to be implemented.")
