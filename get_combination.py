from itertools import product
# class Obj:
#     def __init__(self, catagory, obj):
#         self.catagory = catagory
#         self.catagory.obj = obj

combinations = []

types = {
    "Bed": [
        "16770Dp",
        "Nantucket chaise",
        "2308s",
        "Savanah alumnium chase"
    ],
    "Umbrella": [
        "Outdoor Umbrella 01",
        "Outdoor Umbrella 02"
    ],
    "Table": [
        "Side Table 042",
        "Side Table 129",
        "Side Table 106",
        "Side Table 100"
    ]
}

def sort_by_length(category):
    return len(types[category])

sorted_categories = sorted(types.keys(), key=sort_by_length)

for combo in product(*(types[obj] for obj in sorted_categories)):
    combinations.append(" - ".join(combo))

for result in combinations:
    print(result)
print("Number of Scenes:", len(combinations))