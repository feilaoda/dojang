

class ModelMixin(object):
    def update_model(self, model, attr, required=False, to_int=False):
        value = self.get_argument(attr, '')
        if to_int:
            try:
                value = int(value)
            except:
                value = 0
        if required and value:
            setattr(model, attr, value)
        elif not required:
            setattr(model, attr, value)