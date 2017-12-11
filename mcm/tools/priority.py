import tools.settings as settings


class priority:
    def __init__(self):
        self.blocks = settings.get_value("priority_per_block")

    def priority(self, level):
        if not str(level) in self.blocks:
            return 50000
        else:
            return self.blocks[str(level)]
