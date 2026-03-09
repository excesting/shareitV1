import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('agg')  # Force non-interactive backend
import matplotlib.pyplot as plt
import os
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def load_and_preprocess_data():
    """Load and preprocess the data"""
    try:
        data_path = 'data_set/data.csv'
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Data file not found at {data_path}")
        
        df = pd.read_csv(data_path)
        print(f"Loaded data with columns: {list(df.columns)}")
        
        # Check if we have the required columns
        if 'quantity_stock' not in df.columns:
            raise ValueError("Required column 'quantity_stock' not found in data")
        
        # Use quantity_stock as our target variable since we don't have quantity_sold
        # We'll create a simple time series based on product order
        df = df.sort_values('product_id')
        
        # Extract features for prediction (quantity_stock)
        data = df['quantity_stock'].values.reshape(-1, 1)
        
        # Normalize the data
        scaler = MinMaxScaler(feature_range=(0, 1))
        data_scaled = scaler.fit_transform(data)
        
        print(f"Preprocessed data shape: {data_scaled.shape}")
        return data_scaled, scaler, df
    except Exception as e:
        print(f"Error loading and preprocessing data: {str(e)}")
        return None, None, None

def create_sequences(data, time_steps=3):
    """Create sequences for LSTM model"""
    try:
        X, y = [], []
        for i in range(len(data) - time_steps):
            X.append(data[i:(i + time_steps), 0])
            y.append(data[i + time_steps, 0])
        return np.array(X), np.array(y)
    except Exception as e:
        print(f"Error creating sequences: {str(e)}")
        return None, None

def build_lstm_model(time_steps, features):
    """Build LSTM model with simpler architecture for small datasets"""
    try:
        model = Sequential([
            LSTM(32, return_sequences=True, input_shape=(time_steps, features)),
            LSTM(16, return_sequences=False),
            Dense(8),
            Dense(1)
        ])
        
        model.compile(optimizer='adam', loss='mean_squared_error')
        return model
    except Exception as e:
        print(f"Error building LSTM model: {str(e)}")
        return None

def train_model(model, X_train, y_train, epochs=20, batch_size=2):
    """Train the LSTM model with reduced epochs for small datasets"""
    try:
        # For small datasets, use fewer epochs and smaller batch size
        if len(X_train) < 10:
            epochs = 10
            batch_size = 1
        
        history = model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=0.2,
            verbose=1
        )
        return history
    except Exception as e:
        print(f"Error training model: {str(e)}")
        return None

def evaluate_model(model, X_train, y_train, X_test, y_test, scaler):
    """Evaluate the model and generate predictions"""
    try:
        # Make predictions
        train_predict = model.predict(X_train)
        
        # Inverse transform predictions
        train_predict = scaler.inverse_transform(train_predict)
        y_train_inv = scaler.inverse_transform([y_train])
        
        # Calculate training metrics
        train_rmse = np.sqrt(mean_squared_error(y_train_inv.T, train_predict))
        train_mae = mean_absolute_error(y_train_inv.T, train_predict)
        
        print(f"Training RMSE: {train_rmse:.2f}")
        print(f"Training MAE: {train_mae:.2f}")
        
        # Handle test data if available
        if len(X_test) > 0 and len(y_test) > 0:
            test_predict = model.predict(X_test)
            test_predict = scaler.inverse_transform(test_predict)
            y_test_inv = scaler.inverse_transform([y_test])
            
            # Calculate test metrics
            test_rmse = np.sqrt(mean_squared_error(y_test_inv.T, test_predict))
            test_mae = mean_absolute_error(y_test_inv.T, test_predict)
            
            print(f"Test RMSE: {test_rmse:.2f}")
            print(f"Test MAE: {test_mae:.2f}")
        else:
            test_predict = None
            y_test_inv = None
        
        return train_predict, test_predict, y_train_inv, y_test_inv
    except Exception as e:
        print(f"Error evaluating model: {str(e)}")
        return None, None, None, None

def save_model(model, scaler, filepath='trained_model.pkl'):
    """Save the trained model and scaler"""
    try:
        model_data = {
            'model': model,
            'scaler': scaler
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"Model saved successfully to {filepath}")
        return True
    except Exception as e:
        print(f"Error saving model: {str(e)}")
        return False

def create_visualization(df, train_predict, test_predict, y_train_inv, y_test_inv):
    """Create and save visualization plots"""
    try:
        # Create the plot
        plt.figure(figsize=(12, 6))
        
        # Plot training data
        train_size = len(train_predict)
        plt.plot(range(train_size), y_train_inv.T, label='Actual (Train)', color='blue', marker='o')
        plt.plot(range(train_size), train_predict, label='Predicted (Train)', color='red', marker='s')
        
        # Plot test data if available
        if test_predict is not None and y_test_inv is not None:
            test_size = len(test_predict)
            plt.plot(range(train_size, train_size + test_size), y_test_inv.T, label='Actual (Test)', color='green', marker='o')
            plt.plot(range(train_size, train_size + test_size), test_predict, label='Predicted (Test)', color='orange', marker='s')
        
        plt.title('LSTM Model: Actual vs Predicted Stock Levels', fontsize=16, fontweight='bold')
        plt.xlabel('Product Index', fontsize=12)
        plt.ylabel('Stock Quantity', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Save the plot
        plot_path = 'static/sales_prediction_plot.png'
        plt.savefig(plot_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"Visualization saved to {plot_path}")
        return True
    except Exception as e:
        print(f"Error creating visualization: {str(e)}")
        return False

def main():
    """Main function to train the prediction model"""
    try:
        print("Starting model training process...")
        
        # Step 1: Load and preprocess data
        print("Loading and preprocessing data...")
        data_scaled, scaler, df = load_and_preprocess_data()
        if data_scaled is None:
            print("Failed to load and preprocess data")
            return False
        
        # Check if we have enough data
        if len(data_scaled) < 5:
            print(f"Not enough data for training. Need at least 5 samples, got {len(data_scaled)}")
            return False
        
        # Step 2: Create sequences
        print("Creating sequences for LSTM...")
        time_steps = min(3, len(data_scaled) - 1)  # Adjust time steps for small datasets
        X, y = create_sequences(data_scaled, time_steps)
        if X is None or len(X) == 0:
            print("Failed to create sequences or no sequences generated")
            return False
        
        # Step 3: Split data
        if len(X) < 3:
            print(f"Not enough sequences for training. Need at least 3, got {len(X)}")
            return False
        
        train_size = max(1, int(len(X) * 0.8))  # Ensure at least 1 training sample
        X_train, X_test = X[:train_size], X[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]
        
        # Reshape data for LSTM [samples, time_steps, features]
        X_train = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
        if len(X_test) > 0:
            X_test = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
        
        print(f"Training set size: {len(X_train)}")
        print(f"Test set size: {len(X_test)}")
        
        # Step 4: Build model
        print("Building LSTM model...")
        model = build_lstm_model(time_steps, 1)
        if model is None:
            print("Failed to build model")
            return False
        
        # Step 5: Train model
        print("Training model...")
        history = train_model(model, X_train, y_train, epochs=20, batch_size=2)
        if history is None:
            print("Failed to train model")
            return False
        
        # Step 6: Evaluate model (only if we have test data)
        if len(X_test) > 0:
            print("Evaluating model...")
            train_predict, test_predict, y_train_inv, y_test_inv = evaluate_model(
                model, X_train, y_train, X_test, y_test, scaler)
            
            if train_predict is None:
                print("Failed to evaluate model")
                return False
        else:
            # For very small datasets, just make predictions on training data
            print("Making predictions on training data...")
            train_predict = model.predict(X_train)
            train_predict = scaler.inverse_transform(train_predict)
            y_train_inv = scaler.inverse_transform([y_train])
            test_predict = None
            y_test_inv = None
        
        # Step 7: Save model
        print("Saving model...")
        if not save_model(model, scaler):
            print("Failed to save model")
            return False
        
        # Step 8: Create visualization (only if we have enough data)
        if len(X_train) > 2:
            print("Creating visualization...")
            create_visualization(df, train_predict, test_predict, y_train_inv, y_test_inv)
        
        print("Model training completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("Model training process completed successfully!")
    else:
        print("Model training process failed!")



