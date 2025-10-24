This module creates a new procure method for pull rules in Odoo that search's for another rule that supplyes the destination location for the remaining quantity that the actual rule could't get.
It enables a parallel route for supplyng the same destination making the workflow faster and much more flexible.

The rules will be chained based on secuence number. Works great even with repeated products and even applying different routes on each line.


Use case example:

We got two warehouses WHA and WHB
We got 10 units in WHA/Stock and 5 units in WHB/Stock. Next we place a sale order for 20 units using our route.


Our route would be configured as this: 
Route name: WHA-WHB 
Rule 1:
      Type: Pull
      Operation type: WHA/Deliver
      Source: WHA/Stock
      Destination: Partners/Customers
      Procure Method: mts_transfer_need
      Secuence: 20
Rule 2:
      Operation type: WHB/Deliver
      Source: WHB/Stock
      Destination: Partners/Customers
      Procure Method: make_to_stock
      Secuence:21
      
This would create 2 delivery orders, one for WHA/Stock for 10 units and one for WHB/Stock for 10 units (in witch we got 5 units available).



