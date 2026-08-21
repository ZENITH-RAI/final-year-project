# Car Resell Prediction & Recommendation System - Architecture Diagrams

## 1. Detailed Class Diagram
This diagram maps the exact database schema (with implied data types from SQLAlchemy), the internal structure of the machine learning classes, and the system dependencies. 

```mermaid
classDiagram
    %% Database Models
    class User {
        +Integer id
        +String(100) name
        +String(100) email
        +String password_hash
        +Boolean is_admin
        +check_password(password: str) bool
        +set_password(password: str) void
    }

    class Estimate {
        +Integer id
        +Integer user_id
        +String brand
        +String model
        +Integer year
        +Float km_driven
        +String fuel
        +String seller_type
        +String transmission
        +String owner
        +Float mileage
        +Float engine
        +Float max_power
        +Float seats
        +Float predicted_price
        +Float min_price
        +Float max_price
        +Float actual_price
        +Boolean is_bought
        +Datetime created_at
    }

    %% Machine Learning Components
    class FullPipeline {
        +List~str~ numeric_cols
        +Dict~str, tuple~ mean_std
        +Dict~str, float~ fill_values
        +List~str~ feature_columns
        +List~str~ luxury_brands
        +feature_engineering(df: DataFrame) DataFrame
        +fit(df: DataFrame) DataFrame
        +transform(df: DataFrame) DataFrame
    }

    class SGDRegressor {
        +Float lr
        +Integer epochs
        +Float l2
        +Integer batch_size
        +NDArray coef_
        +Float intercept_
        +fit(X: NDArray, y: NDArray) void
        +partial_fit(X: NDArray, y: NDArray) void
        +predict(X: NDArray) NDArray
    }
    
    class FlaskApplication {
        +Config app.config
        +Lock model_lock
        +initialize_and_train()
        +validate_estimate_form(form_data) Dict
        +record_purchase(estimate, actual_price) bool
        +find_similar_cars(user_input, pred_price) List
    }

    %% Relationships
    User "1" *-- "0..*" Estimate : owns / cascades
    FlaskApplication "1" o-- "1" FullPipeline : instantiates global
    FlaskApplication "1" o-- "1" SGDRegressor : instantiates global
    FullPipeline ..> SGDRegressor : preprocesses input matrix (X) for