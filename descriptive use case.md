**## Table 3.1: Use Case Description for Sign Up / Log In**



**| Field                   | Description                                      |**

**| ----------------------- | ------------------------------------------------ |**

**| \*\*Use Case Identifier\*\* | UC-001                                           |**

**| \*\*Primary Actor\*\*       | User / Administrator                             |**

**| \*\*Secondary Actor\*\*     | None                                             |**

**| \*\*Pre-condition\*\*       | The actor is not logged in.                      |**

**| \*\*Post-condition\*\*      | The actor successfully accesses the system.      |**

**| \*\*Failure Scenario\*\*    | Invalid or incomplete credentials prevent login. |**



**---**



**## Table 3.2: Use Case Description for Predict Resale Price**



**| Field                   | Description                                 |**

**| ----------------------- | ------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-002                                      |**

**| \*\*Primary Actor\*\*       | User                                        |**

**| \*\*Secondary Actor\*\*     | ML Model                                    |**

**| \*\*Pre-condition\*\*       | Required vehicle details are provided.      |**

**| \*\*Post-condition\*\*      | The estimated resale price is displayed.    |**

**| \*\*Failure Scenario\*\*    | Invalid vehicle details prevent prediction. |**



**---**



**## Table 3.3: Use Case Description for View Prediction History**



**| Field                   | Description                                               |**

**| ----------------------- | --------------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-003                                                    |**

**| \*\*Primary Actor\*\*       | User                                                      |**

**| \*\*Secondary Actor\*\*     | Database                                                  |**

**| \*\*Pre-condition\*\*       | The user is logged in.                                    |**

**| \*\*Post-condition\*\*      | Previous predictions are displayed.                       |**

**| \*\*Failure Scenario\*\*    | No prediction history exists or data cannot be retrieved. |**



**---**



**## Table 3.4: Use Case Description for Record Actual Purchase Price**



**| Field                   | Description                                             |**

**| ----------------------- | ------------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-004                                                  |**

**| \*\*Primary Actor\*\*       | User                                                    |**

**| \*\*Secondary Actor\*\*     | Database                                                |**

**| \*\*Pre-condition\*\*       | A saved prediction exists.                              |**

**| \*\*Post-condition\*\*      | The actual purchase price is recorded.                  |**

**| \*\*Failure Scenario\*\*    | Invalid price or missing prediction prevents recording. |**



**---**



**## Table 3.5: Use Case Description for Browse Marketplace**



**| Field                   | Description                           |**

**| ----------------------- | ------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-005                                |**

**| \*\*Primary Actor\*\*       | User                                  |**

**| \*\*Secondary Actor\*\*     | Database                              |**

**| \*\*Pre-condition\*\*       | The marketplace is available.         |**

**| \*\*Post-condition\*\*      | Available car listings are displayed. |**

**| \*\*Failure Scenario\*\*    | Listings cannot be retrieved.         |**



**---**



**## Table 3.6: Use Case Description for View Car Details**



**| Field                   | Description                                      |**

**| ----------------------- | ------------------------------------------------ |**

**| \*\*Use Case Identifier\*\* | UC-006                                           |**

**| \*\*Primary Actor\*\*       | User                                             |**

**| \*\*Secondary Actor\*\*     | Database                                         |**

**| \*\*Pre-condition\*\*       | A valid car listing is selected.                 |**

**| \*\*Post-condition\*\*      | Detailed information about the car is displayed. |**

**| \*\*Failure Scenario\*\*    | The selected listing is unavailable.             |**



**---**



**## Table 3.7: Use Case Description for List Car for Sale**



**| Field                   | Description                                  |**

**| ----------------------- | -------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-007                                       |**

**| \*\*Primary Actor\*\*       | User                                         |**

**| \*\*Secondary Actor\*\*     | Database                                     |**

**| \*\*Pre-condition\*\*       | The user has a valid car prediction.         |**

**| \*\*Post-condition\*\*      | The car is listed in the marketplace.        |**

**| \*\*Failure Scenario\*\*    | Invalid listing details prevent publication. |**



**---**



**## Table 3.8: Use Case Description for Buy Car**



**| Field                   | Description                                     |**

**| ----------------------- | ----------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-008                                          |**

**| \*\*Primary Actor\*\*       | User                                            |**

**| \*\*Secondary Actor\*\*     | Database                                        |**

**| \*\*Pre-condition\*\*       | The selected car is available for sale.         |**

**| \*\*Post-condition\*\*      | A purchase order is created.                    |**

**| \*\*Failure Scenario\*\*    | The car is unavailable or order creation fails. |**



**---**



**## Table 3.9: Use Case Description for Pay via eSewa**



**| Field                   | Description                                         |**

**| ----------------------- | --------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-009                                              |**

**| \*\*Primary Actor\*\*       | User                                                |**

**| \*\*Secondary Actor\*\*     | eSewa Payment Gateway                               |**

**| \*\*Pre-condition\*\*       | A valid purchase order exists.                      |**

**| \*\*Post-condition\*\*      | Successful payment confirms the purchase.           |**

**| \*\*Failure Scenario\*\*    | Payment fails, is cancelled, or cannot be verified. |**



**---**



**## Table 3.10: Use Case Description for View Admin Dashboard**



**| Field                   | Description                                           |**

**| ----------------------- | ----------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-010                                                |**

**| \*\*Primary Actor\*\*       | Administrator                                         |**

**| \*\*Secondary Actor\*\*     | Database                                              |**

**| \*\*Pre-condition\*\*       | The administrator is logged in.                       |**

**| \*\*Post-condition\*\*      | System information is displayed on the dashboard.     |**

**| \*\*Failure Scenario\*\*    | Unauthorized access or data retrieval failure occurs. |**



**---**



**## Table 3.11: Use Case Description for Manage Users \& Predictions**



**| Field                   | Description                                           |**

**| ----------------------- | ----------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-011                                                |**

**| \*\*Primary Actor\*\*       | Administrator                                         |**

**| \*\*Secondary Actor\*\*     | Database                                              |**

**| \*\*Pre-condition\*\*       | The administrator has dashboard access.               |**

**| \*\*Post-condition\*\*      | User and prediction records can be viewed or managed. |**

**| \*\*Failure Scenario\*\*    | Records cannot be accessed or updated.                |**



**---**



**## Table 3.12: Use Case Description for Manage Listings \& Transactions**



**| Field                   | Description                                                   |**

**| ----------------------- | ------------------------------------------------------------- |**

**| \*\*Use Case Identifier\*\* | UC-012                                                        |**

**| \*\*Primary Actor\*\*       | Administrator                                                 |**

**| \*\*Secondary Actor\*\*     | Database                                                      |**

**| \*\*Pre-condition\*\*       | The administrator has dashboard access.                       |**

**| \*\*Post-condition\*\*      | Listings and transaction records can be monitored or managed. |**

**| \*\*Failure Scenario\*\*    | Marketplace or transaction records cannot be retrieved.       |**



