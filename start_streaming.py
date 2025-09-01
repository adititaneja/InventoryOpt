#!/usr/bin/env python3
"""
Startup script for the Inventory Optimization Streaming System
"""

import argparse
import sys
import os
import subprocess
import time
import signal
import threading
from pathlib import Path

def print_banner():
    """Print the system banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        📊 Inventory Optimization Streaming System 🚀         ║
    ║                                                              ║
    ║              Real-time CSV data streaming                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'streamlit', 'pandas', 'numpy', 'watchdog', 'websockets',
        'fastapi', 'uvicorn', 'plotly'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Please install them using: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def start_streamlit_dashboard(port=8501, host="localhost"):
    """Start the Streamlit dashboard"""
    print(f"🚀 Starting Streamlit dashboard on {host}:{port}")
    
    try:
        # Start Streamlit in a subprocess
        cmd = [
            sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
            "--server.port", str(port),
            "--server.address", host
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"✅ Streamlit dashboard started (PID: {process.pid})")
        print(f"🌐 Open your browser and go to: http://{host}:{port}")
        
        return process
        
    except Exception as e:
        print(f"❌ Failed to start Streamlit dashboard: {e}")
        return None

def start_streaming_manager(csv_path=None):
    """Start the streaming data manager"""
    if not csv_path:
        csv_path = "retail_store_inventory.csv"
    
    print(f"📡 Starting streaming manager for: {csv_path}")
    
    try:
        # Import and start the streaming manager
        from streaming_data_manager import CSVStreamingManager
        
        manager = CSVStreamingManager(csv_path)
        
        # Start monitoring
        if manager.start_monitoring():
            print("✅ Streaming manager started successfully")
            print(f"📡 WebSocket server: ws://localhost:8765")
            print(f"📡 Socket.IO server: http://localhost:8766")
            print(f"📡 FastAPI server: http://localhost:8767")
            return manager
        else:
            print("❌ Failed to start streaming manager")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start streaming manager: {e}")
        return None

def start_data_simulation(csv_path=None, update_interval=30, max_updates=None):
    """Start the data simulation in a separate thread"""
    if not csv_path:
        csv_path = "retail_store_inventory.csv"
    
    print(f"🔄 Starting data simulation for: {csv_path}")
    print(f"⏱️  Update interval: {update_interval} seconds")
    print(f"🔄 Updates: {'Infinite' if max_updates is None else max_updates}")
    
    try:
        # Import the simulation function
        from generate_sample_data import simulate_csv_updates
        
        # Create a thread for the simulation
        def run_simulation():
            try:
                simulate_csv_updates(csv_path, update_interval, max_updates)
            except Exception as e:
                print(f"❌ Data simulation error: {e}")
        
        simulation_thread = threading.Thread(target=run_simulation, daemon=True)
        simulation_thread.start()
        
        print("✅ Data simulation started in background")
        return simulation_thread
        
    except Exception as e:
        print(f"❌ Failed to start data simulation: {e}")
        return None

def generate_sample_data():
    """Generate sample data for testing"""
    print("📊 Generating sample inventory data...")
    
    try:
        from generate_sample_data import simulate_csv_updates
        
        # Generate initial data by running one update
        csv_file = "retail_store_inventory.csv"
        if os.path.exists(csv_file):
            print(f"✅ CSV file '{csv_file}' already exists")
            return True
        else:
            print("❌ CSV file not found. Please create 'retail_store_inventory.csv' first.")
            return False
        
    except Exception as e:
        print(f"❌ Failed to generate sample data: {e}")
        return False

def monitor_processes(processes, streaming_manager=None, simulation_thread=None):
    """Monitor running processes and handle cleanup"""
    def signal_handler(signum, frame):
        print("\n🛑 Shutting down...")
        
        # Stop streaming manager if it exists
        if streaming_manager:
            try:
                streaming_manager.stop_monitoring()
                print("✅ Streaming manager stopped")
            except Exception as e:
                print(f"⚠️  Error stopping streaming manager: {e}")
        
        # Terminate subprocesses
        for process in processes:
            if process and hasattr(process, 'terminate'):
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    pass
        
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            time.sleep(1)
            
            # Check if any subprocess has died
            for i, process in enumerate(processes):
                if process and hasattr(process, 'poll') and process.poll() is not None:
                    print(f"⚠️  Process {i} has stopped unexpectedly")
            
            # Check if streaming manager is still running
            if streaming_manager and not streaming_manager.is_running:
                print("⚠️  Streaming manager has stopped")
                break
            
            # Check if simulation thread is still alive
            if simulation_thread and not simulation_thread.is_alive():
                print("⚠️  Data simulation thread has stopped")
                
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Inventory Optimization Streaming System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start everything with default settings
  python start_streaming.py

  # Start with custom CSV file
  python start_streaming.py --csv my_data.csv

  # Start only the dashboard
  python start_streaming.py --dashboard-only

  # Start only the streaming manager
  python start_streaming.py --streaming-only

  # Start with data simulation
  python start_streaming.py --simulate-data

  # Start with custom simulation settings
  python start_streaming.py --simulate-data --update-interval 15 --max-updates 20

  # Generate sample data
  python start_streaming.py --generate-data

  # Custom port for dashboard
  python start_streaming.py --port 8502
        """
    )
    
    parser.add_argument(
        '--csv', '-c',
        type=str,
        help='Path to CSV file to monitor'
    )
    
    parser.add_argument(
        '--dashboard-only', '-d',
        action='store_true',
        help='Start only the Streamlit dashboard'
    )
    
    parser.add_argument(
        '--streaming-only', '-s',
        action='store_true',
        help='Start only the streaming manager'
    )
    
    parser.add_argument(
        '--simulate-data', '--sim',
        action='store_true',
        help='Start data simulation alongside other services'
    )
    
    parser.add_argument(
        '--update-interval', '-i',
        type=int,
        default=30,
        help='Data update interval in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--max-updates', '-m',
        type=int,
        default=None,
        help='Maximum number of data updates (default: infinite)'
    )
    
    parser.add_argument(
        '--generate-data', '-g',
        action='store_true',
        help='Generate sample data and exit'
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8501,
        help='Port for Streamlit dashboard (default: 8501)'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='Host for Streamlit dashboard (default: localhost)'
    )
    
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Check dependencies and exit'
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Check dependencies if requested
    if args.check_deps:
        check_dependencies()
        return
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Generate sample data if requested
    if args.generate_data:
        if generate_sample_data():
            print("✅ Sample data ready!")
        else:
            print("❌ Failed to prepare sample data")
            sys.exit(1)
        return
    
    # Start components based on arguments
    processes = []  # This will only contain subprocess objects
    streaming_manager = None
    simulation_thread = None
    
    try:
        if not args.streaming_only:
            # Start Streamlit dashboard
            dashboard_process = start_streamlit_dashboard(args.port, args.host)
            if dashboard_process:
                processes.append(dashboard_process)
                time.sleep(3)  # Give dashboard time to start
        
        if not args.dashboard_only:
            # Start streaming manager
            csv_path = args.csv or "retail_store_inventory.csv"
            
            # Check if CSV exists
            if not Path(csv_path).exists():
                print(f"📁 CSV file '{csv_path}' not found.")
                print("Please ensure the file exists before starting the streaming system.")
                sys.exit(1)
            
            streaming_manager = start_streaming_manager(csv_path)
            if streaming_manager:
                # Note: streaming_manager is NOT added to processes list
                # It's handled separately because it's not a subprocess
                pass
        
        # Start data simulation if requested
        if args.simulate_data:
            csv_path = args.csv or "retail_store_inventory.csv"
            simulation_thread = start_data_simulation(
                csv_path, 
                args.update_interval, 
                args.max_updates
            )
        
        if not processes and not args.simulate_data and not streaming_manager:
            print("❌ No components started. Use --help for options.")
            sys.exit(1)
        
        # Print status
        print("\n" + "="*60)
        print("🎯 System Status:")
        
        if not args.streaming_only:
            print(f"   📊 Dashboard: http://{args.host}:{args.port}")
        
        if not args.dashboard_only:
            print("   📡 Streaming Manager: Active")
            print("   🔌 WebSocket: ws://localhost:8765")
            print("   🔌 Socket.IO: http://localhost:8766")
            print("   🔌 FastAPI: http://localhost:8767")
        
        if args.simulate_data:
            print("   🔄 Data Simulation: Active")
            print(f"   ⏱️  Update Interval: {args.update_interval} seconds")
            print(f"   🔄 Max Updates: {'Infinite' if args.max_updates is None else args.max_updates}")
        
        print("="*60)
        print("💡 Press Ctrl+C to stop all services")
        print("="*60)
        
        # Monitor processes
        monitor_processes(processes, streaming_manager, simulation_thread)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if streaming_manager:
            try:
                streaming_manager.stop_monitoring()
                print("✅ Streaming manager stopped")
            except Exception as e:
                print(f"⚠️  Error stopping streaming manager: {e}")
        
        # Cleanup subprocesses
        for process in processes:
            if process and hasattr(process, 'terminate'):
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    pass
        
        print("👋 All services stopped")

if __name__ == "__main__":
    main() 