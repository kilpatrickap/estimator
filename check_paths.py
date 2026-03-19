import os
p1 = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic\Atlantic Catering'
p2 = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic\Atlantic Catering\Project Database'
print(f"P1 (root) has Priced BOQs: {os.path.exists(os.path.join(p1, 'Priced BOQs'))}")
print(f"P2 (sub) has Priced BOQs: {os.path.exists(os.path.join(p2, 'Priced BOQs'))}")
