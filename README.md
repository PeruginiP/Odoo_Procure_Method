This module creates a new procure method for pull rules in Odoo that search's for another rule that supplyes the destination location for the remaining quantity that the actual rule could't get.
It enables a parallel route for supplyng the same destination making the workflow faster.

Use case example:

We got three warehouses WHA, WHB, and WHC
We got 10 units in WHA/Stock, 5 units in WHB/Stock and 3 units in WHC.

Next we place a sale order for 25 units.

We want to create 3 picking orders, one for WHA/Stock for 10 units, one for WHB/Stock for 5 units, one for WHC/Stock for 3 units and one purchase order for the remaining qty.

