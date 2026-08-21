# Module Description

## Car Resell Price Prediction and Recommendation System

The system is a Flask-based decision-support application that estimates a used car's resale value in NPR, shows a price range, recommends comparable records, stores estimates for authenticated users, allows owners to list a predicted car in a small marketplace, and uses eSewa ePay V2 for test/UAT payments. It remains an academic marketplace prototype rather than a vehicle-inspection or legal valuation service.

## 1. User and Authentication Module

This module manages registration, login, logout, user sessions, password hashing, and role-based access. A normal user can save and review only their own estimates. An administrator can access summary and record pages. Protected actions use authentication and CSRF checks.

**Inputs:** name, email, password, login credentials.  
**Outputs:** authenticated session, profile access, authorized actions.  
**Main data entity:** `User(id, name, email, password_hash, is_admin, created_at)`.

## 2. Vehicle Catalog and Validation Module

The module reads vehicle brands and models from the project dataset and fallback catalog. It guides the user while entering brand and model, validates categorical choices, and checks numerical ranges before prediction. This prevents invalid feature values from reaching the model.

**Inputs:** brand, model, year, kilometers driven, fuel, seller type, transmission, owner, mileage, engine, maximum power, seats.  
**Outputs:** canonicalized vehicle values or field-level error messages.

## 3. Data Preparation and Feature Engineering Module

The project loads `UsedCars.csv`, removes the `torque` column, removes duplicate records, extracts `brand` and `model` from `name`, converts mileage/engine/power strings to numeric values, and removes the lowest and highest 1% of selling-price values. The selling price is converted to NPR using the project multiplier of 2.2.

The module creates these engineered features:

- `car_age = current_year - year`
- `km_per_year = km_driven / (car_age + 1)`
- `is_7_seater`
- `engine_power_ratio`
- `power_per_cc`
- `is_luxury`

Categorical attributes are one-hot encoded. Numeric values are mean-imputed and standardized. The training feature set is retained so prediction inputs can be aligned safely.

## 4. Price Prediction Module

The module uses a custom mini-batch stochastic gradient descent regressor. It trains on `log(1 + selling_price)` and converts predictions back with `expm1`. The model trains for 450 epochs with a learning-rate schedule, L2 regularization, and batch size 32. The application computes MAE, MSE, RMSE, R², and MAPE on an 80:20 train-test split.

**Output:** predicted price, minimum estimated price, and maximum estimated price. The range is calculated with MAE:

```text
minimum = max(0, predicted_price - MAE)
maximum = predicted_price + MAE
```

## 5. Recommendation Module

The recommendation module helps users interpret the prediction by showing up to five comparable dataset records. It first filters by brand and fuel. If this is too restrictive, it falls back to fuel and transmission. Records are ranked by differences in year, engine capacity, and price relative to the prediction.

**Output per recommendation:** vehicle name, year, fuel, transmission, mileage, historical selling price, and difference from the prediction.

## 6. Estimate History Module

An authenticated prediction is stored as an `Estimate` record, including the vehicle specifications, predicted/minimum/maximum prices, and date. Users can view their own history in descending date order. Keeping the full submitted specifications enables future learning from confirmed prices.

## 7. Marketplace and eSewa Payment Module

An authenticated user can convert one saved `Estimate` into one marketplace `Listing`. The predicted value becomes the listing price, while the seller adds location, contact information, description, condition notes, and optional vehicle images. Other users can browse active listings, apply filters, open a vehicle detail page, and initiate a purchase. A seller cannot purchase their own listing.

When the buyer chooses **Buy now with eSewa**, the backend creates an `Order` and `Payment`, generates a unique transaction UUID, reserves the listing, and signs the eSewa ePay V2 request with HMAC-SHA256. The browser is redirected to eSewa. On return, the application verifies the signed success response and checks the transaction again with eSewa's server-side status API. Only a verified `COMPLETE` response changes the order to `PAID` and the listing to `SOLD`. Failed or cancelled transactions release the listing; pending transactions remain unconfirmed.

**Main entities:** `Listing`, `ListingImage`, `Order`, and `Payment`.

## 8. Administration Module

The administration module provides a restricted dashboard with counts of users and predictions, average predicted price, recent estimates, marketplace totals, listing records, and transaction records. It is intended for monitoring the academic project rather than for a production operations workflow.

## 9. Module Interaction

```text
User input
   -> Catalog and validation
   -> Data preparation and feature engineering
   -> SGD price prediction
   -> Price range + recommendation
   -> Save estimate (authenticated user)
   -> Profile history
   -> Optional seller marketplace listing
   -> Buyer order
   -> eSewa ePay V2
   -> Signed callback + status verification
   -> Paid order / sold listing
```
