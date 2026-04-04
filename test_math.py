import sys
old_o = 15.0
old_p = 10.0
new_o = 20.0
new_p = 15.0

subtotal = 1000.0
overhead1 = subtotal * (old_o / 100.0)
profit1 = (subtotal + overhead1) * (old_p / 100.0)
gross1 = subtotal + overhead1 + profit1

print(f"Gross 1: {gross1}")

old_multiplier = (1 + old_o / 100.0) * (1 + old_p / 100.0)
new_multiplier = (1 + new_o / 100.0) * (1 + new_p / 100.0)
scale_factor = new_multiplier / old_multiplier

gross_migrated = gross1 * scale_factor
print(f"Gross Migrated: {gross_migrated}")

overhead2 = subtotal * (new_o / 100.0)
profit2 = (subtotal + overhead2) * (new_p / 100.0)
gross2 = subtotal + overhead2 + profit2

print(f"Gross 2: {gross2}")
