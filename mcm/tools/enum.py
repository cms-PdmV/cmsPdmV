def Enum(*sequential, **named):
    enums = dict(list(zip(sequential, list(range(len(sequential))))), **named)
    return type('Enum', (), enums)