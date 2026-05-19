"""Optional utility placeholder.
Use this if you replace config/production_regions_2025.csv with a new PSA production Excel.
Because PSA Excel layouts can change, the recommended workflow is:
1) clean the new PSA workbook into columns: area_group, psa_region, province, coconut_mature_2025_mt, share_pct
2) replace config/production_regions_2025.csv
3) keep location_id/lat/lon columns from the existing config.
"""
print(__doc__)
