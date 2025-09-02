from itertools import product
# class Obj:
#     def __init__(self, catagory, obj):
#         self.catagory = catagory
#         self.catagory.obj = obj

combinations = []

types = {
    "Bed":[
       "First"
    ],
    "Umbrella":[
     "Big",
     "Small"
    ],
    "Table":[
       "Square",
       "Round"
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