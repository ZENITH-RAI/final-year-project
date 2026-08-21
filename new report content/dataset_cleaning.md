# Dataset Cleaning and Preparation

## Dataset Overview

The source file is `UsedCars.csv`. It contains 8,135 rows and 13 original columns:

`name`, `year`, `selling_price`, `km_driven`, `fuel`, `seller_type`, `transmission`, `owner`, `mileage`, `engine`, `max_power`, `torque`, and `seats`.

The project uses this file as historical used-car data. Its price values are multiplied by 2.2 in the application to present results in NPR.

## Cleaning Steps Used in the Project

1. Load the CSV file using pandas.
2. Multiply `selling_price` by 2.2 to convert the project price representation to NPR.
3. Drop `torque`, because its values have inconsistent text formats and it is not used by the prediction pipeline.
4. Remove exact duplicate rows.
5. Extract `brand` as the first token of `name` and create `model` from the remaining tokens.
6. Convert `mileage`, `engine`, and `max_power` from text with units into numeric values.
7. Remove extreme selling-price records below the 1st percentile and above the 99th percentile.
8. Retain the 25 most frequent model names; replace less frequent models with `Other` to reduce sparse categories.
9. Create `brand_model` by joining brand and cleaned model.
10. Split the cleaned data into 80% training and 20% testing data using a fixed random seed.

## Conversion Rules

| Field | Raw examples | Cleaning rule | Result |
|---|---|---|---|
| `mileage` | `23.4 kmpl` | Remove ` kmpl`, then numeric conversion | Float kmpl |
| `engine` | `1248 CC` | Remove ` CC`, then numeric conversion | Float CC |
| `max_power` | `74 bhp` | Remove ` bhp`, then numeric conversion | Float bhp |
| `name` | `Maruti Swift Dzire VDI` | First token = brand, remainder = model | `Maruti`, `Swift Dzire VDI` |
| `selling_price` | historical dataset amount | Multiply by 2.2 | NPR-oriented target |

## Missing Values

String-to-number conversion may produce missing values when units or source text are malformed. The model pipeline handles numeric missing values by replacing them with each feature's mean computed from the training data. This avoids dropping all rows that contain a missing numeric field while ensuring test/prediction data are transformed with training statistics.

## Outlier Treatment

Extreme price observations can dominate a regression model. The project uses quantile trimming rather than a fixed price threshold:

```python
q1 = df['selling_price'].quantile(0.01)
q99 = df['selling_price'].quantile(0.99)
df = df[(df['selling_price'] >= q1) & (df['selling_price'] <= q99)]
```

This removes the bottom 1% and top 1% of prices after currency conversion. This decision should be reported as a modelling choice, since it may remove rare but genuine luxury or very low-value vehicles.

## Feature Engineering After Cleaning

The cleaned dataset is enriched with car age, kilometers per year, seating indicator, engine-to-power ratios, and luxury-brand status. Categorical fields are one-hot encoded; numerical columns are standardized by training mean and standard deviation.

## Limitations and Recommended Improvements

- The dataset should be verified for its country, period, and currency before using values as Nepal market evidence.
- `name` token splitting is imperfect for multi-word brands and should be replaced by an explicit brand dictionary.
- Vehicle condition, city, accident history, service record, listing date, and image information are absent.
- More robust treatment may include median imputation, explicit missingness indicators, and model-specific outlier comparisons.
- Cleaning statistics and random split indices should be saved to support reproducibility.
