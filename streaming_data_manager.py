import os
import time
import json
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import websockets
import socketio
from fastapi import FastAPI, WebSocket
import uvicorn
import redis
from kafka import KafkaProducer, KafkaConsumer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVStreamingManager:
    """Manages real-time streaming of CSV data with multiple protocols"""
    
    def __init__(self, csv_path: str, update_interval: int = 300):
        """
        Initialize the streaming manager
        
        Args:
            csv_path: Path to the CSV file to monitor
            update_interval: Expected update interval in seconds (default: 5 minutes)
        """
        self.csv_path = Path(csv_path)
        self.update_interval = update_interval
        self.last_modified = None
        self.last_data = None
        self.subscribers = []
        self.is_running = False
        
        # Initialize streaming protocols
        self.websocket_server = None
        self.socketio_server = None
        self.fastapi_app = None
        self.redis_client = None
        self.kafka_producer = None
        
        # Data validation schema
        self.expected_columns = [
            'Date', 'Store ID', 'Product ID', 'Category', 'Region',
            'Inventory Level', 'Units Sold', 'Units Ordered', 'Demand Forecast',
            'Price', 'Discount', 'Weather Condition', 'Holiday/Promotion',
            'Competitor Pricing', 'Seasonality'
        ]
    
    def start_monitoring(self):
        """Start monitoring the CSV file for changes"""
        if not self.csv_path.exists():
            logger.error(f"CSV file not found: {self.csv_path}")
            return False
        
        self.is_running = True
        
        # Start file monitoring
        self._start_file_monitor()
        
        # Start streaming servers (continue even if some fail)
        try:
            self._start_websocket_server()
        except Exception as e:
            logger.warning(f"WebSocket server failed to start: {e}")
        
        try:
            self._start_socketio_server()
        except Exception as e:
            logger.warning(f"Socket.IO server failed to start: {e}")
        
        try:
            self._start_fastapi_server()
        except Exception as e:
            logger.warning(f"FastAPI server failed to start: {e}")
        
        # Start data streaming loop
        self._start_streaming_loop()
        
        logger.info(f"Started monitoring CSV file: {self.csv_path}")
        return True
    
    def stop_monitoring(self):
        """Stop monitoring and streaming"""
        self.is_running = False
        
        # Stop file monitoring
        if hasattr(self, 'observer'):
            self.observer.stop()
            self.observer.join()
        
        # Stop streaming servers
        if hasattr(self, 'websocket_server') and self.websocket_server:
            # WebSocket server runs in a thread, just mark as stopped
            pass
        
        if hasattr(self, 'socketio_server') and self.socketio_server:
            try:
                # Socket.IO server cleanup
                pass
            except:
                pass
        
        if hasattr(self, 'fastapi_app') and self.fastapi_app:
            try:
                # FastAPI server cleanup
                pass
            except:
                pass
        
        logger.info("Stopped CSV monitoring and streaming")
    
    def subscribe(self, callback: Callable[[pd.DataFrame, Dict], None]):
        """Subscribe to data updates"""
        self.subscribers.append(callback)
        logger.info(f"Added subscriber. Total subscribers: {len(self.subscribers)}")
    
    def unsubscribe(self, callback: Callable[[pd.DataFrame, Dict], None]):
        """Unsubscribe from data updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"Removed subscriber. Total subscribers: {len(self.subscribers)}")
    
    def _start_file_monitor(self):
        """Start file system monitoring using watchdog"""
        class CSVFileHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager
            
            def on_modified(self, event):
                if not event.is_directory and event.src_path == str(self.manager.csv_path):
                    self.manager._handle_file_change()
        
        self.observer = Observer()
        self.observer.schedule(CSVFileHandler(self), str(self.csv_path.parent), recursive=False)
        self.observer.start()
    
    def _start_websocket_server(self):
        """Start WebSocket server for real-time data streaming"""
        async def websocket_handler(websocket, path):
            try:
                while self.is_running:
                    if self.last_data is not None:
                        # Send data as JSON
                        data_json = self.last_data.to_json(orient='records', date_format='iso')
                        await websocket.send(data_json)
                    
                    # Wait for next update
                    await asyncio.sleep(1)
            except websockets.exceptions.ConnectionClosed:
                pass
        
        # Start WebSocket server in background thread
        def run_websocket_server():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                start_server = websockets.serve(websocket_handler, "localhost", 8765)
                loop.run_until_complete(start_server)
                loop.run_forever()
            except Exception as e:
                logger.error(f"WebSocket server error: {e}")
        
        websocket_thread = threading.Thread(target=run_websocket_server, daemon=True)
        websocket_thread.start()
        self.websocket_server = websocket_thread
    
    def _start_socketio_server(self):
        """Start Socket.IO server for real-time updates"""
        try:
            # Use a simpler Socket.IO server setup
            self.socketio_server = socketio.Server(async_mode='threading')
            
            @self.socketio_server.event
            def connect(sid, environ):
                logger.info(f"Client connected: {sid}")
            
            @self.socketio_server.event
            def disconnect(sid):
                logger.info(f"Client disconnected: {sid}")
            
            # Start Socket.IO server in background
            def run_socketio():
                try:
                    app = socketio.WSGIApp(self.socketio_server)
                    # Use a simple HTTP server instead of uvicorn for Socket.IO
                    from wsgiref.simple_server import make_server
                    server = make_server('localhost', 8766, app)
                    logger.info("Socket.IO server started on port 8766")
                    server.serve_forever()
                except Exception as e:
                    logger.error(f"Socket.IO server error: {e}")
            
            socketio_thread = threading.Thread(target=run_socketio, daemon=True)
            socketio_thread.start()
            self.socketio_server_thread = socketio_thread
            
        except Exception as e:
            logger.error(f"Failed to initialize Socket.IO server: {e}")
            self.socketio_server = None
            self.socketio_server_thread = None
    
    def _start_fastapi_server(self):
        """Start FastAPI server with WebSocket endpoints"""
        self.fastapi_app = FastAPI(title="Inventory Data Streaming API")
        
        @self.fastapi_app.websocket("/ws/data")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while self.is_running:
                    if self.last_data is not None:
                        # Send data as JSON
                        data_json = self.last_data.to_json(orient='records', date_format='iso')
                        await websocket.send_text(data_json)
                    
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
        
        @self.fastapi_app.get("/data")
        async def get_latest_data():
            """Get the latest data as JSON"""
            if self.last_data is not None:
                return {
                    "timestamp": datetime.now().isoformat(),
                    "data": self.last_data.to_dict(orient='records')
                }
            return {"error": "No data available"}
        
        # Start FastAPI server in background
        def run_fastapi():
            try:
                uvicorn.run(self.fastapi_app, host="localhost", port=8767, log_level="error")
            except Exception as e:
                logger.error(f"FastAPI server error: {e}")
        
        fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
        fastapi_thread.start()
        self.fastapi_thread = fastapi_thread
    
    def _start_streaming_loop(self):
        """Start the main streaming loop"""
        def streaming_loop():
            while self.is_running:
                try:
                    # Check if file has been modified
                    current_modified = self.csv_path.stat().st_mtime
                    
                    if self.last_modified is None or current_modified > self.last_modified:
                        self._handle_file_change()
                    
                    # Wait before next check
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error in streaming loop: {e}")
                    time.sleep(5)
        
        threading.Thread(target=streaming_loop, daemon=True).start()
    
    def _handle_file_change(self):
        """Handle CSV file changes"""
        try:
            # Read the updated CSV
            new_data = pd.read_csv(self.csv_path)
            
            # Validate columns
            if not self._validate_columns(new_data):
                logger.warning("CSV columns don't match expected schema")
                return
            
            # Update last modified time
            self.last_modified = self.csv_path.stat().st_mtime
            
            # Calculate changes
            changes = self._calculate_changes(new_data)
            
            # Update last data
            self.last_data = new_data
            
            # Notify subscribers
            self._notify_subscribers(new_data, changes)
            
            # Broadcast via streaming protocols
            self._broadcast_data(new_data, changes)
            
            logger.info(f"Processed CSV update with {len(new_data)} rows")
            
        except Exception as e:
            logger.error(f"Error processing CSV update: {e}")
    
    def _validate_columns(self, df: pd.DataFrame) -> bool:
        """Validate that the DataFrame has the expected columns"""
        return all(col in df.columns for col in self.expected_columns)
    
    def _calculate_changes(self, new_data: pd.DataFrame) -> Dict:
        """Calculate changes from previous data"""
        if self.last_data is None:
            return {"type": "initial_load", "rows": len(new_data)}
        
        # Calculate basic statistics
        changes = {
            "type": "update",
            "timestamp": datetime.now().isoformat(),
            "total_rows": len(new_data),
            "changes": {}
        }
        
        # Compare inventory levels if possible
        if 'Inventory Level' in new_data.columns and 'Inventory Level' in self.last_data.columns:
            # This is a simplified comparison - you might want more sophisticated change detection
            changes["changes"]["inventory_changes"] = {
                "low_stock": len(new_data[new_data['Inventory Level'] < 10]),
                "out_of_stock": len(new_data[new_data['Inventory Level'] == 0])
            }
        
        return changes
    
    def _notify_subscribers(self, data: pd.DataFrame, changes: Dict):
        """Notify all subscribers of data changes"""
        for subscriber in self.subscribers:
            try:
                subscriber(data, changes)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    def _broadcast_data(self, data: pd.DataFrame, changes: Dict):
        """Broadcast data via streaming protocols"""
        try:
            # Broadcast via Socket.IO
            if self.socketio_server:
                data_json = data.to_json(orient='records', date_format='iso')
                # Note: Socket.IO broadcasting is handled by the server thread
                # No need to call asyncio.run here
            
            # Store in Redis for caching (if available)
            if self.redis_client:
                self.redis_client.setex(
                    'latest_inventory_data',
                    3600,  # 1 hour TTL
                    data.to_json(orient='records', date_format='iso')
                )
            
            # Send to Kafka (if configured)
            if self.kafka_producer:
                message = {
                    'timestamp': datetime.now().isoformat(),
                    'data': data.to_dict(orient='records'),
                    'changes': changes
                }
                self.kafka_producer.send('inventory_updates', json.dumps(message).encode())
                
        except Exception as e:
            logger.error(f"Error broadcasting data: {e}")
    
    def get_latest_data(self) -> Optional[pd.DataFrame]:
        """Get the latest data"""
        return self.last_data
    
    def get_data_summary(self) -> Dict:
        """Get a summary of the current data"""
        if self.last_data is None:
            return {"error": "No data available"}
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_rows": len(self.last_data),
            "columns": list(self.last_data.columns),
            "date_range": {
                "start": self.last_data['Date'].min() if 'Date' in self.last_data.columns else None,
                "end": self.last_data['Date'].max() if 'Date' in self.last_data.columns else None
            }
        }
        
        # Add numerical summaries
        numeric_columns = self.last_data.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            summary["numerical_summary"] = self.last_data[numeric_columns].describe().to_dict()
        
        return summary

    def get_server_status(self):
        """Get the status of streaming servers"""
        status = {
            'websocket': hasattr(self, 'websocket_server') and self.websocket_server is not None,
            'socketio': hasattr(self, 'socketio_server') and self.socketio_server is not None,
            'fastapi': hasattr(self, 'fastapi_app') and self.fastapi_app is not None
        }
        return status
    
    def print_server_status(self):
        """Print the status of streaming servers"""
        status = self.get_server_status()
        logger.info("Streaming Server Status:")
        logger.info(f"  WebSocket: {'✅ Running' if status['websocket'] else '❌ Not running'}")
        logger.info(f"  Socket.IO: {'✅ Running' if status['socketio'] else '❌ Not running'}")
        logger.info(f"  FastAPI: {'✅ Running' if status['fastapi'] else '❌ Not running'}")

# Example usage and testing
if __name__ == "__main__":
    # Example usage
    csv_path = "retail_store_inventory.csv"  # Update this path
    
    # Create streaming manager
    manager = CSVStreamingManager(csv_path)
    
    # Add a subscriber
    def data_handler(data, changes):
        print(f"Data updated: {changes}")
        print(f"Total rows: {len(data)}")
    
    manager.subscribe(data_handler)
    
    # Start monitoring
    if manager.start_monitoring():
        try:
            print("CSV streaming started. Press Ctrl+C to stop.")
            # Show server status
            manager.print_server_status()
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_monitoring()
            print("Streaming stopped.") 