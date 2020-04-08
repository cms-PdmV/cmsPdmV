import json


class ValidationStorage():
    def __init__(self, filename='validations.json'):
        self.filename = filename

    def save(self, key, dict_to_save):
        all_items = self.get_all()
        all_items[key] = dict_to_save
        with open(self.filename, 'w') as f:
            f.write(json.dumps(all_items, indent=2, sort_keys=True))

    def get(self, key):
        return self.get_all().get(key)

    def get_all(self):
        with open(self.filename, 'r') as f:
            all_items = json.loads(f.read())

        return all_items

    def delete(self, key):
        all_items = self.get_all()
        if key in all_items:
            del all_items[key]
            with open(self.filename, 'w') as f:
                f.write(json.dumps(all_items, indent=2, sort_keys=True))