import streamlit as st
import pandas as pd
import plotly.express as px
import os


st.set_page_config(page_title="Inventory Dashboard", layout="wide")

class Dashboard:
    def __init__(self):
        self.csv_path = None
        self.data = None
        self.reorder_point = 100
        self.safety_stock = 45
        self.filtered_data = None
        self.latest_data = None

        if 'data_loaded' not in st.session_state:
            st.session_state.data_loaded = False
        if 'reorder_point' not in st.session_state:
            st.session_state.reorder_point = self.reorder_point
        if 'safety_stock' not in st.session_state:
            st.session_state.safety_stock = self.safety_stock
    
    def setup_sidebar(self):
        st.sidebar.title("Configuration")
        
        # Auto-detect CSV file
        if os.path.exists("retail_store_inventory.csv") and self.csv_path is None:
            self.csv_path = "retail_store_inventory.csv"
            if not st.session_state.data_loaded:
                self.load_data()
        
        # File upload
        uploaded_file = st.sidebar.file_uploader("Upload CSV", type=['csv'])
        if uploaded_file is not None:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                self.csv_path = tmp_file.name
            self.load_data()

        # Reorder Point Parameter
        st.sidebar.subheader("Inventory Parameters")
        self.reorder_point = st.sidebar.slider(
            "Reorder Point", 
            min_value=0, 
            max_value=1000, 
            value=st.session_state.reorder_point,
            step=10,
            help="Inventory level at which to reorder"
        )
        st.session_state.reorder_point = self.reorder_point
        
        self.safety_stock = st.sidebar.slider(
            "Safety Stock", 
            min_value=0, 
            max_value=500, 
            value=st.session_state.safety_stock,
            step=5,
            help="Minimum inventory level to maintain as safety buffer"
        )
        st.session_state.safety_stock = self.safety_stock

        # Refresh button
        if st.sidebar.button("Refresh"):
            if self.csv_path:
                self.load_data()
                st.rerun()
    
    def load_data(self):
        try:
            if self.csv_path is None:
                st.error("No CSV file specified")
                return False
            
            if not os.path.exists(self.csv_path):
                st.error(f"CSV file not found: {self.csv_path}")
                return False
                
            self.data = pd.read_csv(self.csv_path)
            if self.data.empty:
                st.error("CSV file is empty")
                return False
                
            self.filtered_data = self.data
            self.latest_data = self.data
            st.session_state.data_loaded = True
            return True
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return False
    
    def display_metrics(self, data):
        """Display metrics with filters and KPI cards"""
        if data is None:
            st.warning("No data available to display metrics")
            return
        
        # Setup filters and apply them
        selected_store, selected_product = self._setup_metric_filters(data)
        filtered_data, latest_data = self._apply_metric_filters(data, selected_store, selected_product)
        
        # Store as instance variables for use in other functions
        self.filtered_data = filtered_data
        self.latest_data = latest_data
        
        # Calculate and display metrics
        metrics = self._calculate_metrics(latest_data)
        self._display_metric_cards(metrics)

    def _setup_metric_filters(self, data):
        """Setup store and product filters for metrics"""
        col1, col2 = st.columns(2)
        
        with col1:
            all_stores = ['All Stores'] + sorted(data['Store ID'].unique().tolist())
            selected_store = st.selectbox("Select Store ID:", all_stores)
        
        with col2:
            all_products = ['All Products'] + sorted(data['Product ID'].unique().tolist())
            selected_product = st.selectbox("Select Product ID:", all_products)
        
        return selected_store, selected_product

    def _apply_metric_filters(self, data, selected_store, selected_product):
        """Apply store and product filters to data"""
        # Filter data based on selection
        if selected_product == 'All Products' and selected_store == 'All Stores':
            filtered_data = data
        elif selected_product == 'All Products':
            filtered_data = data[data['Store ID'] == selected_store]
        elif selected_store == 'All Stores':
            filtered_data = data[data['Product ID'] == selected_product]
        else:
            filtered_data = data[(data['Product ID'] == selected_product) & (data['Store ID'] == selected_store)]
        
        # Get the last date for each Product ID and Store ID combination
        if 'Date' in filtered_data.columns:
            filtered_data['Date'] = pd.to_datetime(filtered_data['Date'])
            latest_data = filtered_data.sort_values('Date').groupby(['Product ID', 'Store ID']).tail(1)
        else:
            latest_data = filtered_data
        
        return filtered_data, latest_data

    def _calculate_metrics(self, latest_data):
        """Calculate KPI metrics from filtered data"""
        latest_data['Revenue'] = latest_data['Units Sold'] * latest_data['Price']
        
        return {
            'total_products': len(latest_data['Product ID'].unique()),
            'total_stores': len(latest_data['Store ID'].unique()),
            'total_inventory': latest_data['Inventory Level'].sum() if 'Inventory Level' in latest_data.columns else 0,
            'low_stock': len(latest_data[latest_data['Inventory Level'] < self.reorder_point]) if 'Inventory Level' in latest_data.columns else 0,
            'out_of_stock': len(latest_data[latest_data['Inventory Level'] == 0]) if 'Inventory Level' in latest_data.columns else 0,
            'total_revenue': latest_data['Revenue'].sum() if 'Revenue' in latest_data.columns else 0
        }

    def _display_metric_cards(self, metrics):
        """Display metric cards in a grid layout"""
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        col1.metric("Total Stores", metrics['total_stores'])
        col2.metric("Total Products", metrics['total_products'])
        col3.metric("Total Inventory Units", metrics['total_inventory'])
        col4.metric("Total Revenue", f"${metrics['total_revenue']:,.0f}")
        col5.metric("Low Stock Products", metrics['low_stock'])
        col6.metric("Out of Stock Products", metrics['out_of_stock'])
        
    def display_charts(self, data):
        """Display charts with date filtering"""
        if data is None:
            st.warning("No data available to display charts")
            return
        
        # Setup date filters and get filtered data
        chart_data = self._setup_chart_date_filters(data)
        
        # Display charts in columns
        col1, col2 = st.columns(2)
        
        with col1:
            self._create_inventory_demand_chart(chart_data)
        
        with col2:
            self._create_units_chart(chart_data)

    def _setup_chart_date_filters(self, data):
        """Setup date filters for charts and return filtered data"""
        if 'Date' not in data.columns:
            return data
        
        # Convert Date to datetime for filtering
        chart_data = data.copy()
        chart_data['Date'] = pd.to_datetime(chart_data['Date'])
        
        # Get min and max dates
        min_date = chart_data['Date'].min()
        max_date = chart_data['Date'].max()
        
        # Date range selector
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("Start Date", value=max_date - pd.Timedelta(days=30), min_value=min_date, max_value=max_date)
        with col_date2:
            end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
        
        # Filter data by date range
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        return chart_data[(chart_data['Date'] >= start_date) & (chart_data['Date'] <= end_date)]

    def _create_inventory_demand_chart(self, chart_data):
        """Create inventory and demand forecast chart"""
        if 'Date' not in chart_data.columns or 'Inventory Level' not in chart_data.columns:
            return
        
        if len(chart_data) == 0:
            st.info("No data available for selected date range")
            return
        
        # Group by date and sum all metrics
        daily_metrics = chart_data.groupby('Date').agg({
            'Inventory Level': 'sum',
            'Demand Forecast': 'sum'
        }).reset_index()
        
        # Create a line plot with multiple metrics
        fig = px.line(daily_metrics, x='Date', y=['Inventory Level', 'Demand Forecast'], 
                    title='Inventory & Demand Forecast Over Time')
        
        # Add horizontal line for reorder point
        fig.add_hline(y=self.reorder_point, line_dash="dash", line_color="red", 
                     annotation_text=f"Reorder Point ({self.reorder_point})")
        
        # Add horizontal line for safety stock
        fig.add_hline(y=self.safety_stock, line_dash="dot", line_color="orange", 
                     annotation_text=f"Safety Stock ({self.safety_stock})")
        
        self._apply_chart_styling(fig)
        st.plotly_chart(fig, use_container_width=True, key="inventory_demand_chart")

    def _create_units_chart(self, chart_data):
        """Create units sold and ordered chart"""
        if 'Date' not in chart_data.columns or 'Inventory Level' not in chart_data.columns:
            return
        
        if len(chart_data) == 0:
            st.info("No data available for selected date range")
            return
        
        # Group by date and sum all metrics
        daily_metrics = chart_data.groupby('Date').agg({
            'Units Sold': 'sum',
            'Units Ordered': 'sum'
        }).reset_index()
        
        # Create a line plot with multiple metrics
        fig = px.line(daily_metrics, x='Date', y=['Units Sold', 'Units Ordered'], 
                    title='Units Sold & Ordered Over Time')
        
        # Add horizontal line for average units sold
        avg_units_sold = daily_metrics['Units Sold'].mean()
        fig.add_hline(y=avg_units_sold, line_dash="dash", line_color="orange", 
                     annotation_text=f"Avg Units Sold ({avg_units_sold:.1f})")
        
        self._apply_chart_styling(fig)
        st.plotly_chart(fig, use_container_width=True, key="units_sold_ordered_chart")

    def _apply_chart_styling(self, fig):
        """Apply consistent styling to charts"""
        fig.update_layout(
            title_x=0.3,
            title_font_size=16,
            title_font_color="black"
        )

    def display_overview(self):
        """Display overview dashboard with key metrics and navigation"""
        # Calculate key metrics
        overview_metrics = self._calculate_overview_metrics()
        
        # Display key metrics in a clean layout
        self._display_overview_metrics(overview_metrics)
        
        # Display navigation section
        self._display_navigation_links()
        
        # Display recent activity or summary
        self._display_recent_summary()

    def _calculate_overview_metrics(self):
        """Calculate key overview metrics"""
        if self.data is None:
            return None
        
        # Basic metrics
        total_stores = len(self.data['Store ID'].unique())
        total_skus = len(self.data['Product ID'].unique())
        total_categories = len(self.data['Category'].unique()) if 'Category' in self.data.columns else 0
        
        # Revenue metrics (last year)
        if 'Date' in self.data.columns and 'Units Sold' in self.data.columns and 'Price' in self.data.columns:
            self.data['Date'] = pd.to_datetime(self.data['Date'])
            self.data['Revenue'] = self.data['Units Sold'] * self.data['Price']
            
            # Last year data
            current_year = pd.Timestamp.now().year
            last_year_data = self.data[self.data['Date'].dt.year == current_year - 1]
            total_revenue_last_year = last_year_data['Revenue'].sum() if len(last_year_data) > 0 else 0
            
            # Current year data
            current_year_data = self.data[self.data['Date'].dt.year == current_year]
            total_revenue_current_year = current_year_data['Revenue'].sum() if len(current_year_data) > 0 else 0
            
            # Revenue growth
            revenue_growth = ((total_revenue_current_year - total_revenue_last_year) / total_revenue_last_year * 100) if total_revenue_last_year > 0 else 0
        else:
            total_revenue_last_year = 0
            total_revenue_current_year = 0
            revenue_growth = 0
        
        # Inventory metrics
        if 'Inventory Level' in self.data.columns:
            total_inventory = self.data['Inventory Level'].sum()
            low_stock_items = len(self.data[self.data['Inventory Level'] < self.reorder_point])
            out_of_stock_items = len(self.data[self.data['Inventory Level'] == 0])
        else:
            total_inventory = 0
            low_stock_items = 0
            out_of_stock_items = 0
        
        return {
            'total_stores': total_stores,
            'total_skus': total_skus,
            'total_categories': total_categories,
            'total_revenue_last_year': total_revenue_last_year,
            'total_revenue_current_year': total_revenue_current_year,
            'revenue_growth': revenue_growth,
            'total_inventory': total_inventory,
            'low_stock_items': low_stock_items,
            'out_of_stock_items': out_of_stock_items
        }

    def _display_overview_metrics(self, metrics):
        """Display overview metrics in a clean layout"""
        if metrics is None:
            st.warning("No data available to display overview metrics")
            return
        
        st.subheader("📈 Key Performance Indicators")
        
        # Main metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🏪 Total Stores", 
                f"{metrics['total_stores']:,}",
                help="Number of unique stores in the system"
            )
        
        with col2:
            st.metric(
                "📦 Total SKUs", 
                f"{metrics['total_skus']:,}",
                help="Number of unique products/SKUs"
            )
        
        with col3:
            st.metric(
                "📊 Total Categories", 
                f"{metrics['total_categories']:,}",
                help="Number of product categories"
            )
        
        with col4:
            st.metric(
                "📦 Total Inventory", 
                f"{metrics['total_inventory']:,}",
                help="Total inventory units across all stores"
            )
        
        # Revenue metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Last Year Revenue", 
                f"${metrics['total_revenue_last_year']:,.0f}",
                help="Total revenue from previous year"
            )
        
        with col2:
            st.metric(
                "💰 Current Year Revenue", 
                f"${metrics['total_revenue_current_year']:,.0f}",
                help="Total revenue from current year"
            )
        
        with col3:
            growth_color = "normal" if metrics['revenue_growth'] >= 0 else "inverse"
            st.metric(
                "📈 Revenue Growth", 
                f"{metrics['revenue_growth']:+.1f}%",
                delta_color=growth_color,
                help="Revenue growth compared to last year"
            )
        
        with col4:
            st.metric(
                "⚠️ Low Stock Items", 
                f"{metrics['low_stock_items']:,}",
                help="Items below reorder point"
            )

    def _display_navigation_links(self):
        """Display navigation links to all tabs and sub-tabs"""
        st.markdown("---")
        st.subheader("🧭 Quick Navigation")
        
        # Inventory Analysis Section
        st.markdown("### 📦 Inventory Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📈 Overall Inventory", key="nav_overall_inventory", use_container_width=True):
                st.info("🎯 **Navigate to:** '📦 Store Inventory Analysis' tab → '📈 Overall Inventory'")
        
        with col2:
            if st.button("🏪 Store & Product Level", key="nav_store_product", use_container_width=True):
                st.info("🎯 **Navigate to:** '📦 Store Inventory Analysis' tab → '🏪 Store & Product Level Inventory'")
        
        # Sales Analysis Section
        st.markdown("### 💰 Sales Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📈 Time-Based Sales**")
            if st.button("📅 Daily Analysis", key="nav_daily_sales", use_container_width=True):
                st.info("🎯 **Navigate to:** '💰 Sales Analysis' tab → '📅 Daily Analysis'")
        
        with col2:
            st.markdown("**🏪 Store & Product Analysis**")
            if st.button("🏪 Store Analysis", key="nav_store_analysis", use_container_width=True):
                st.info("🎯 **Navigate to:** '💰 Sales Analysis' tab → '🏪 Store & Product Analysis'")

    def _display_recent_summary(self):
        """Display recent activity or summary information"""
        st.subheader("📋 Recent Summary")
        st.markdown("---")
        
        if self.data is None:
            st.info("No data available for summary")
            return
        
        # Get latest date
        if 'Date' in self.data.columns:
            latest_date = pd.to_datetime(self.data['Date']).max()
            st.markdown(f"**📅 Latest Data Date:** {latest_date.strftime('%B %d, %Y')}")
        
        # Data freshness indicator
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"📊 **{len(self.data):,}** Total Records")
        
        with col2:
            if 'Date' in self.data.columns:
                date_range = pd.to_datetime(self.data['Date'])
                days_span = (date_range.max() - date_range.min()).days
                st.info(f"📅 **{days_span}** Days of Data")
        
        with col3:
            st.info(f"🔄 **Real-time** Updates")

                         
    def display_inventory_by_category(self, data):
        if data is None:
            st.warning("No data available to display category analysis")
            return
            
        col1, col2 = st.columns(2)
        
        with col1:
             if 'Category' in data.columns and 'Inventory Level' in data.columns:
                 # Calculate latest inventory by category - first get unique combinations, then sum by category
                 unique_inventory = data[['Store ID', 'Product ID', 'Category', 'Inventory Level']].drop_duplicates(subset=['Store ID', 'Product ID', 'Category'])
                 category_inventory = unique_inventory.groupby('Category')['Inventory Level'].sum().reset_index()
                 
                 # Create bar chart for inventory by category
                 fig = px.bar(category_inventory, x='Category', y='Inventory Level', 
                             title='Latest Inventory by Category')
                 
                 # Add data labels on top of bars with smart formatting
                 fig.update_traces(
                     texttemplate='%{text}', 
                     textposition='outside',
                     text=[self._format_number_for_display(y) for y in category_inventory['Inventory Level']]
                 )
                 
                 fig.update_layout(
                     title_x=0.3,
                     title_font_size=16,
                     title_font_color="black",
                     xaxis=dict(showgrid=False),
                     yaxis=dict(showgrid=False)
                 )
                 st.plotly_chart(fig, use_container_width=True, key="category_inventory_chart")
        
        with col2:
            if 'Region' in data.columns and 'Inventory Level' in data.columns:
                 # Calculate latest inventory by region - first get unique combinations, then sum by region
                 unique_inventory = data[['Store ID', 'Product ID', 'Region', 'Inventory Level']].drop_duplicates(subset=['Store ID', 'Product ID', 'Region'])
                 region_inventory = unique_inventory.groupby('Region')['Inventory Level'].sum().reset_index()
                 
                 # Create bar chart for inventory by region
                 fig = px.bar(region_inventory, x='Region', y='Inventory Level', 
                             title='Latest Inventory by Region')
                 
                 # Add data labels on top of bars with smart formatting
                 fig.update_traces(
                     texttemplate='%{text}', 
                     textposition='outside',
                     text=[self._format_number_for_display(y) for y in region_inventory['Inventory Level']]
                 )
                 
                 fig.update_layout(
                     title_x=0.3,
                     title_font_size=16,
                     title_font_color="black",
                     xaxis=dict(showgrid=False),
                     yaxis=dict(showgrid=False)
                 )
                 st.plotly_chart(fig, use_container_width=True, key="region_inventory_chart")
    
    def display_inventory_by_store(self, data):
        
        # Store inventory by category chart at the bottom
        st.subheader("🏪 Inventory by Store and Category")
        if 'Store ID' in data.columns and 'Category' in data.columns:
            # Store inventory by category - show each unique store-category combination
            store_inventory = data[['Store ID', 'Category', 'Inventory Level']].drop_duplicates(subset=['Store ID', 'Category'])
            fig = px.bar(store_inventory, x='Store ID', y='Inventory Level', 
                        color='Category', title="")
            
            fig.update_traces(
                texttemplate='%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in store_inventory['Inventory Level']]
            )
            
            fig.update_layout(
                title_x=0.3,
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="overall_store_inventory_chart")
 
    def _calculate_revenue_differences(self, data, period_column, revenue_column):
        """Calculate revenue differences from previous period for trend analysis"""
        # Sort by period to ensure correct order
        data_sorted = data.sort_values(period_column)
        
        # Calculate difference from previous period
        data_sorted['Revenue_Diff'] = data_sorted.groupby('Category')[revenue_column].diff()
        
        # Calculate percentage change
        data_sorted['Revenue_Pct_Change'] = data_sorted.groupby('Category')[revenue_column].pct_change() * 100
        
        return data_sorted

    def _format_number_for_display(self, value):
        """Format numbers for display in data labels - show as integer, K (thousands), or M (millions)"""
        if pd.isna(value) or value == 0:
            return "0"
        
        abs_value = abs(value)
        
        if abs_value >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif abs_value >= 1_000:
            return f"{value/1_000:.1f}K"
        else:
            return f"{value:,.0f}"

    def _setup_time_based_filters(self, revenue_data):
        """Setup Store and Product filters for time-based analysis"""
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            if 'Store ID' in revenue_data.columns:
                all_stores = ['All Stores'] + sorted(revenue_data['Store ID'].unique().tolist())
                selected_store_filter = st.selectbox("Select Store:", all_stores, key="time_store_filter")
            else:
                selected_store_filter = 'All Stores'
        
        with col_filter2:
            if 'Product ID' in revenue_data.columns:
                all_products = ['All Products'] + sorted(revenue_data['Product ID'].unique().tolist())
                selected_product_filter = st.selectbox("Select Product:", all_products, key="time_product_filter")
            else:
                selected_product_filter = 'All Products'
        
        # Apply Store and Product filters to revenue_data
        filtered_revenue_data = revenue_data.copy()
        if selected_store_filter != 'All Stores':
            filtered_revenue_data = filtered_revenue_data[filtered_revenue_data['Store ID'] == selected_store_filter]
        if selected_product_filter != 'All Products':
            filtered_revenue_data = filtered_revenue_data[filtered_revenue_data['Product ID'] == selected_product_filter]
        
        return filtered_revenue_data

    def _display_kpis(self, data, period_type):
        """Display KPIs for a given time period"""
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        with col_kpi1:
            total_revenue = data['Revenue'].sum()
            st.metric("Total Revenue", f"${total_revenue:,.0f}")
        
        with col_kpi2:
            total_units = data['Units Sold'].sum()
            st.metric("Total Units Sold", f"{total_units:,.0f}")
        
        with col_kpi3:
            # Calculate average revenue from aggregated data for the period
            if period_type == 'D':
                period_data = data.groupby(data['Date'].dt.to_period('D'))['Revenue'].sum()
            elif period_type == 'W':
                period_data = data.groupby(data['Date'].dt.to_period('W'))['Revenue'].sum()
            elif period_type == 'M':
                period_data = data.groupby(data['Date'].dt.to_period('M'))['Revenue'].sum()
            elif period_type == 'Y':
                period_data = data.groupby(data['Date'].dt.to_period('Y'))['Revenue'].sum()
            
            avg_period_revenue = period_data.mean()
            period_name = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Y': 'Yearly'}[period_type]
            st.metric(f"Average {period_name} Revenue", f"${avg_period_revenue:,.0f}")
        
        with col_kpi4:
            avg_price = data['Price'].mean()
            st.metric("Average Price", f"${avg_price:,.2f}")

    def _display_daily_analysis(self, filtered_revenue_data):
        """Display daily sales analysis tab"""
        
        # Date range filter for daily analysis (default: last 1 month)
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date = st.date_input("Start Date", 
                                     value=(filtered_revenue_data['Date'].max() - pd.Timedelta(days=30)).date(), 
                                     min_value=filtered_revenue_data['Date'].min().date(), 
                                     max_value=filtered_revenue_data['Date'].max().date(), key="daily_start")
        with col_date2:
            end_date = st.date_input("End Date", 
                                   value=filtered_revenue_data['Date'].max().date(), 
                                   min_value=filtered_revenue_data['Date'].min().date(), 
                                   max_value=filtered_revenue_data['Date'].max().date(), key="daily_end")
        
        # Filter data by date range on top of store/product filters
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        filtered_daily_data = filtered_revenue_data[(filtered_revenue_data['Date'] >= start_date) & (filtered_revenue_data['Date'] <= end_date)]
        
        # KPIs at the top
        self._display_kpis(filtered_daily_data, 'D')
        
        # Daily sales by category
        if 'Category' in filtered_daily_data.columns:
            daily_category = filtered_daily_data.groupby([filtered_daily_data['Date'].dt.to_period('D'), 'Category'])['Revenue'].sum().reset_index()
            daily_category['Date'] = daily_category['Date'].astype(str)
            fig = px.bar(daily_category, x='Date', y='Revenue', 
                        color='Category', title='Daily Sales Revenue by Category')
            
            # Add data labels on top of bars with smart formatting
            fig.update_traces(
                texttemplate='$%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in daily_category['Revenue']]
            )
            
            fig.update_layout(
                title_x=0.3,
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="daily_category_chart")
        
        # Daily revenue differences by category
        if 'Category' in filtered_daily_data.columns:
            daily_revenue_diff = filtered_daily_data.groupby([filtered_daily_data['Date'].dt.to_period('D'), 'Category'])['Revenue'].sum().reset_index()
            daily_revenue_diff['Date'] = daily_revenue_diff['Date'].astype(str)
            
            # Calculate revenue differences
            daily_revenue_diff = self._calculate_revenue_differences(daily_revenue_diff, 'Date', 'Revenue')
            
            # Filter out first day (no difference to show)
            daily_revenue_diff = daily_revenue_diff[daily_revenue_diff['Revenue_Diff'].notna()]
            
            if len(daily_revenue_diff) > 0:
                fig = px.bar(daily_revenue_diff, x='Date', y='Revenue_Diff', 
                            color='Category', title='Daily Revenue Change from Previous Day')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='%{text}', 
                    textposition='outside',
                    text=[f"${self._format_number_for_display(y)}" for y in daily_revenue_diff['Revenue_Diff']]
                )
                
                # Add horizontal line at y=0 for reference
                fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="daily_revenue_diff_chart")
            else:
                st.info("Insufficient data to show daily revenue differences")

    def _display_weekly_analysis(self, filtered_revenue_data):
        """Display weekly sales analysis tab"""        
        # Week selection filter for weekly analysis (default: last 4 weeks)
        col_week1, col_week2 = st.columns(2)
        
        # Get unique weeks from the data
        weekly_periods = sorted(filtered_revenue_data['Date'].dt.to_period('W').unique())
        week_labels = [f"W {period.asfreq('D').strftime('%Y-%m-%d')}" for period in weekly_periods]
        
        with col_week1:
            start_week_idx = max(0, len(weekly_periods) - 4)  # Default to last 4 weeks
            start_week = st.selectbox("Start Week:", week_labels, index=start_week_idx, key="weekly_start")
        with col_week2:
            end_week_idx = len(weekly_periods) - 1  # Default to most recent week
            end_week = st.selectbox("End Week:", week_labels, index=end_week_idx, key="weekly_end")
        
        # Convert selected weeks back to datetime for filtering
        start_week_period = weekly_periods[week_labels.index(start_week)]
        end_week_period = weekly_periods[week_labels.index(end_week)]
        
        # Filter data by week range on top of store/product filters
        filtered_weekly_data = filtered_revenue_data[
            (filtered_revenue_data['Date'].dt.to_period('W') >= start_week_period) & 
            (filtered_revenue_data['Date'].dt.to_period('W') <= end_week_period)
        ]
        
        # KPIs at the top
        self._display_kpis(filtered_weekly_data, 'W')
        
        # Weekly sales by category
        if 'Category' in filtered_weekly_data.columns:
            weekly_category = filtered_weekly_data.groupby([filtered_weekly_data['Date'].dt.to_period('W'), 'Category'])['Revenue'].sum().reset_index()
            weekly_category['Week'] = weekly_category['Date'].apply(lambda x: f"{x.asfreq('D').strftime('%Y-%m-%d')}")
            fig = px.bar(weekly_category, x='Week', y='Revenue', 
                        color='Category', title='Weekly Sales Revenue by Category')
            
            # Add data labels on top of bars with smart formatting
            fig.update_traces(
                texttemplate='$%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in weekly_category['Revenue']]
            )
            
            fig.update_layout(
                title_x=0.3,
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="weekly_category_chart")
        
        # Weekly revenue differences by category
        if 'Category' in filtered_weekly_data.columns:
            weekly_revenue_diff = filtered_weekly_data.groupby([filtered_weekly_data['Date'].dt.to_period('W'), 'Category'])['Revenue'].sum().reset_index()
            weekly_revenue_diff['Week'] = weekly_revenue_diff['Date'].apply(lambda x: f"W {x.asfreq('D').strftime('%Y-%m-%d')}")
            
            # Calculate revenue differences
            weekly_revenue_diff = self._calculate_revenue_differences(weekly_revenue_diff, 'Week', 'Revenue')
            
            # Filter out first week (no difference to show)
            weekly_revenue_diff = weekly_revenue_diff[weekly_revenue_diff['Revenue_Diff'].notna()]
            
            if len(weekly_revenue_diff) > 0:
                fig = px.bar(weekly_revenue_diff, x='Week', y='Revenue_Diff', 
                            color='Category', title='Weekly Revenue Change from Previous Week')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='%{text}', 
                    textposition='outside',
                    text=[f"${self._format_number_for_display(y)}" for y in weekly_revenue_diff['Revenue_Diff']]
                )
                
                # Add horizontal line at y=0 for reference
                fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="weekly_revenue_diff_chart")
            else:
                st.info("Insufficient data to show weekly revenue differences")

    def _display_monthly_analysis(self, filtered_revenue_data):
        """Display monthly sales analysis tab"""
        
        # Month selection filter for monthly analysis (default: past year)
        col_month1, col_month2 = st.columns(2)
        
        # Get unique months from the data
        monthly_periods = sorted(filtered_revenue_data['Date'].dt.to_period('M').unique())
        month_labels = [period.strftime('%B %Y') for period in monthly_periods]
        
        with col_month1:
            start_month_idx = max(0, len(monthly_periods) - 12)  # Default to last 12 months
            start_month = st.selectbox("Start Month:", month_labels, index=start_month_idx, key="monthly_start")
        with col_month2:
            end_month_idx = len(monthly_periods) - 1  # Default to most recent month
            end_month = st.selectbox("End Month:", month_labels, index=end_month_idx, key="monthly_end")
        
        # Convert selected months back to period for filtering
        start_month_period = monthly_periods[month_labels.index(start_month)]
        end_month_period = monthly_periods[month_labels.index(end_month)]
        
        # Filter data by month range on top of store/product filters
        filtered_monthly_data = filtered_revenue_data[
            (filtered_revenue_data['Date'].dt.to_period('M') >= start_month_period) & 
            (filtered_revenue_data['Date'].dt.to_period('M') <= end_month_period)
        ]
        
        # KPIs at the top
        self._display_kpis(filtered_monthly_data, 'M')
        
        # Monthly sales by category
        if 'Category' in filtered_monthly_data.columns:
            monthly_category = filtered_monthly_data.groupby([filtered_monthly_data['Date'].dt.to_period('M'), 'Category'])['Revenue'].sum().reset_index()
            monthly_category['Month'] = monthly_category['Date'].astype(str)
            fig = px.bar(monthly_category, x='Month', y='Revenue', 
                        color='Category', title='Monthly Sales Revenue by Category')
            
            # Add data labels on top of bars with smart formatting
            fig.update_traces(
                texttemplate='$%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in monthly_category['Revenue']]
            )
            
            fig.update_layout(
                title_x=0.3,    
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="monthly_category_chart")
        
        # Monthly revenue differences by category
        if 'Category' in filtered_monthly_data.columns:
            monthly_revenue_diff = filtered_monthly_data.groupby([filtered_monthly_data['Date'].dt.to_period('M'), 'Category'])['Revenue'].sum().reset_index()
            monthly_revenue_diff['Month'] = monthly_revenue_diff['Date'].astype(str)
            
            # Calculate revenue differences
            monthly_revenue_diff = self._calculate_revenue_differences(monthly_revenue_diff, 'Month', 'Revenue')
            
            # Filter out first month (no difference to show)
            monthly_revenue_diff = monthly_revenue_diff[monthly_revenue_diff['Revenue_Diff'].notna()]
            
            if len(monthly_revenue_diff) > 0:
                fig = px.bar(monthly_revenue_diff, x='Month', y='Revenue_Diff', 
                            color='Category', title='Monthly Revenue Change from Previous Month')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='%{text}', 
                    textposition='outside',
                    text=[f"${self._format_number_for_display(y)}" for y in monthly_revenue_diff['Revenue_Diff']]
                )
                
                # Add horizontal line at y=0 for reference
                fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="monthly_revenue_diff_chart")
            else:
                st.info("Insufficient data to show monthly revenue differences")

    def _display_yearly_analysis(self, filtered_revenue_data):
        """Display yearly sales analysis tab"""        
        # Year selection filter for yearly analysis (default: past 3 years)
        col_year1, col_year2 = st.columns(2)
        
        # Get unique years from the data
        yearly_periods = sorted(filtered_revenue_data['Date'].dt.to_period('Y').unique())
        year_labels = [str(period.year) for period in yearly_periods]
        
        with col_year1:
            start_year_idx = max(0, len(yearly_periods) - 3)  # Default to last 3 years
            start_year = st.selectbox("Start Year:", year_labels, index=start_year_idx, key="yearly_start")
        with col_year2:
            end_year_idx = len(yearly_periods) - 1  # Default to most recent year
            end_year = st.selectbox("End Year:", year_labels, index=end_year_idx, key="yearly_end")
        
        # Convert selected years back to period for filtering
        start_year_period = yearly_periods[year_labels.index(start_year)]
        end_year_period = yearly_periods[year_labels.index(end_year)]
        
        # Filter data by year range on top of store/product filters
        filtered_yearly_data = filtered_revenue_data[
            (filtered_revenue_data['Date'].dt.to_period('Y') >= start_year_period) & 
            (filtered_revenue_data['Date'].dt.to_period('Y') <= end_year_period)
        ]
        
        # KPIs at the top
        self._display_kpis(filtered_yearly_data, 'Y')
        
        # Yearly sales by category
        if 'Category' in filtered_yearly_data.columns:
            yearly_category = filtered_yearly_data.groupby([filtered_yearly_data['Date'].dt.to_period('Y'), 'Category'])['Revenue'].sum().reset_index()
            yearly_category['Year'] = yearly_category['Date'].astype(str)
            fig = px.bar(yearly_category, x='Year', y='Revenue', 
                        color='Category', title='Yearly Sales Revenue by Category')
            
            # Add data labels on top of bars with smart formatting
            fig.update_traces(
                texttemplate='$%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in yearly_category['Revenue']]
            )
            
            fig.update_layout(
                title_x=0.3,
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="yearly_category_chart")
        
        # Yearly revenue differences by category
        if 'Category' in filtered_yearly_data.columns:
            yearly_revenue_diff = filtered_yearly_data.groupby([filtered_yearly_data['Date'].dt.to_period('Y'), 'Category'])['Revenue'].sum().reset_index()
            yearly_revenue_diff['Year'] = yearly_revenue_diff['Date'].astype(str)
            
            # Calculate revenue differences
            yearly_revenue_diff = self._calculate_revenue_differences(yearly_revenue_diff, 'Year', 'Revenue')
            
            # Filter out first year (no difference to show)
            yearly_revenue_diff = yearly_revenue_diff[yearly_revenue_diff['Revenue_Diff'].notna()]
            
            if len(yearly_revenue_diff) > 0:
                fig = px.bar(yearly_revenue_diff, x='Year', y='Revenue_Diff', 
                            color='Category', title='Yearly Revenue Change from Previous Year')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='%{text}', 
                    textposition='outside',
                    text=[f"${self._format_number_for_display(y)}" for y in yearly_revenue_diff['Revenue_Diff']]
                )
                
                # Add horizontal line at y=0 for reference
                fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="yearly_revenue_diff_chart")
            else:
                st.info("Insufficient data to show yearly revenue differences")

    def _display_time_based_analysis(self, revenue_data):
        """Display time-based sales analysis with all time period tabs"""
        if 'Date' not in revenue_data.columns:
            st.warning("Date column not available for time-based analysis")
            return
        
        # Convert Date to datetime
        revenue_data['Date'] = pd.to_datetime(revenue_data['Date'])
        
        # Setup filters and get filtered data
        filtered_revenue_data = self._setup_time_based_filters(revenue_data)
        
        # Create sub-tabs for different time periods
        daily_tab, weekly_tab, monthly_tab, yearly_tab = st.tabs(["📅 Daily", "📊 Weekly", "📈 Monthly", "📋 Yearly"])
        
        with daily_tab:
            self._display_daily_analysis(filtered_revenue_data)
        
        with weekly_tab:
            self._display_weekly_analysis(filtered_revenue_data)
        
        with monthly_tab:
            self._display_monthly_analysis(filtered_revenue_data)
        
        with yearly_tab:
            self._display_yearly_analysis(filtered_revenue_data)

    def _display_store_product_analysis(self, revenue_data):
        """Display store and product analysis tab"""
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Store ID' in revenue_data.columns and 'Category' in revenue_data.columns:
                store_category_revenue = revenue_data.groupby(['Store ID', 'Category'])['Revenue'].sum().reset_index()
                fig = px.bar(store_category_revenue, x='Store ID', y='Revenue', 
                            color='Category', title='Revenue by Store and Category')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='$%{text}', 
                    textposition='outside',
                    text=[self._format_number_for_display(y) for y in store_category_revenue['Revenue']]
                )
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="store_category_chart")
        
        with col2:
            if 'Product ID' in revenue_data.columns and 'Category' in revenue_data.columns:
                product_category_revenue = revenue_data.groupby(['Product ID', 'Category'])['Revenue'].sum().reset_index()
                # Show top 3 products by category
                top_products_by_category = product_category_revenue.groupby('Category').apply(
                    lambda x: x.nlargest(3, 'Revenue')).reset_index(drop=True)
                fig = px.bar(top_products_by_category, x='Product ID', y='Revenue', 
                            color='Category', title='Top 3 Products by Category')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='$%{text}', 
                    textposition='outside',
                    text=[self._format_number_for_display(y) for y in top_products_by_category['Revenue']]
                )
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="top_products_category_chart")
                
        # Revenue by Category and Seasonality
        col3, col4 = st.columns(2)
        
        with col3:
            if 'Category' in revenue_data.columns:
                category_revenue = revenue_data.groupby('Category')['Revenue'].sum().reset_index()
                fig = px.pie(category_revenue, values='Revenue', names='Category', 
                            title='Revenue by Category')
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black"
                )
                st.plotly_chart(fig, use_container_width=True, key="category_revenue_chart")
        
        with col4:
            if 'Seasonality' in revenue_data.columns:
                seasonal_revenue = revenue_data.groupby('Seasonality')['Revenue'].sum().reset_index()
                fig = px.bar(seasonal_revenue, x='Seasonality', y='Revenue', 
                            title='Revenue by Seasonality')
                
                # Add data labels on top of bars with smart formatting
                fig.update_traces(
                    texttemplate='$%{text}', 
                    textposition='outside',
                    text=[self._format_number_for_display(y) for y in seasonal_revenue['Revenue']]
                )
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="seasonal_revenue_chart")

    def display_sales_analysis(self):
        """Main method to display sales analysis dashboard"""
        if self.filtered_data is None:
            st.warning("No data available to display sales analysis")
            return
        
        # Calculate revenue for all analysis
        if 'Units Sold' in self.filtered_data.columns and 'Price' in self.filtered_data.columns:
            revenue_data = self.filtered_data.copy()
            revenue_data['Revenue'] = revenue_data['Units Sold'] * revenue_data['Price']
            
            # Create tabs for different time aggregations
            time_tab1, time_tab2 = st.tabs(["📈 Time-Based Sales", "🏪 Store & Product Analysis"])
            
            with time_tab1:
                self._display_time_based_analysis(revenue_data)
            
            with time_tab2:
                self._display_store_product_analysis(revenue_data)
        else:
            st.warning("Revenue data not available. Please ensure 'Units Sold' and 'Price' columns exist.")

    def _display_overall_inventory_analysis(self, filtered_inventory_data):
        """Display overall inventory analysis with metrics, charts, and table"""
        # Display components with filtered data
        self.display_metrics(filtered_inventory_data)
        self.display_charts(filtered_inventory_data)
        self.display_inventory_by_store(filtered_inventory_data)
        self.display_inventory_by_category(filtered_inventory_data)

    def _display_store_product_inventory_analysis(self, filtered_inventory_data):
        """Display store and product level inventory analysis with tabs"""
        if 'Store ID' in filtered_inventory_data.columns:
            all_stores = sorted(filtered_inventory_data['Store ID'].unique().tolist())
            if all_stores:
                # Select first store as default
                default_store_idx = 0
                selected_store = st.selectbox("Select Store:", all_stores, index=default_store_idx, key="store_product_store_filter")
                
                # Filter data based on store selection
                filtered_store_data = filtered_inventory_data[filtered_inventory_data['Store ID'] == selected_store]
                st.info(f"📊 Showing inventory data for Store: {selected_store}")
            else:
                filtered_store_data = filtered_inventory_data
                st.warning("No stores available in the data")
        else:
            filtered_store_data = filtered_inventory_data
            st.warning("Store ID column not available for filtering")
        
        # Create tabs for better organization
        tab1, tab2 = st.tabs(["📦 Inventory Detail", "🚚 Orders in Transit"])
        
        with tab1:
            self._display_inventory_detail_tab(filtered_store_data)
        
        with tab2:
            self._display_orders_in_transit_tab(selected_store)

    def _display_inventory_table_with_orders(self, detailed_inventory):
        """Display inventory table with Place Order buttons for each row"""
        st.dataframe(detailed_inventory, use_container_width=True, hide_index=True)
        
        # Place Order button below the table
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("📦 Place Order", type="primary", key="place_order_bottom_button", use_container_width=True):
                st.session_state['show_order_popup'] = True
                st.session_state['order_data'] = detailed_inventory
                st.rerun()
        
        # Display order popup if triggered
        if st.session_state.get('show_order_popup', False):
            self._show_order_popup()

    def _show_order_popup(self):
        """Display popup for order details"""
        # Create a modal-like popup using columns and containers
        st.markdown("### 📋 Place Order")
        
        # Get the order data from session state
        order_data = st.session_state.get('order_data', None)
        
        if order_data is not None:
            # Order form
            with st.form(key="order_form"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    store_id = st.selectbox(
                        "Store ID:",
                        options=sorted(order_data['Store ID'].unique()),
                        key="popup_store_select"
                    )
                
                with col2:
                    # Filter products by selected store
                    store_products = order_data[order_data['Store ID'] == store_id]['Product ID'].unique()
                    product_id = st.selectbox(
                        "Product ID:",
                        options=sorted(store_products),
                        key="popup_product_select"
                    )
                
                with col3:
                    # Get the selected row data and display inventory info
                    if store_id and product_id:
                        selected_row_data = order_data[
                            (order_data['Store ID'] == store_id) & 
                            (order_data['Product ID'] == product_id)
                        ]
                        
                        if len(selected_row_data) > 0:
                            row_data = selected_row_data.iloc[0]
                            st.write(f"**Current Inventory:** {row_data['Inventory Level']:,.0f}")
                            st.write(f"**Status:** {row_data['Status']}")
                            st.write(f"**Category:** {row_data['Category']}")
                            st.write(f"**Price:** ${row_data['Price']:.2f}")
                        else:
                            st.write("**No data available**")
                            st.write("**Status:** N/A")
                            st.write("**Category:** N/A")
                            st.write("**Price:** N/A")
                    else:
                        st.write("**Select Store & Product**")
                        st.write("**Status:** N/A")
                        st.write("**Category:** N/A")
                        st.write("**Price:** N/A")
                
                st.markdown("---")
                
                # Order details
                col1, col2 = st.columns(2)
                with col1:
                    order_quantity = st.number_input(
                        "Order Quantity:", 
                        min_value=1, 
                        value=1, 
                        step=1,
                        key="popup_quantity",
                        help="Enter the quantity to order"
                    )
                
                with col2:
                    # Vendor selection (you can customize this list)
                    vendors = ["Vendor A", "Vendor B", "Vendor C", "Preferred Supplier", "Local Supplier"]
                    selected_vendor = st.selectbox(
                        "Select Vendor:", 
                        options=vendors,
                        key="popup_vendor",
                        help="Choose a vendor for this order"
                    )
                
                # Additional order details
                delivery_date = st.date_input(
                    "Expected Delivery Date:",
                    value=(pd.Timestamp.now() + pd.Timedelta(days=7)).date(),
                    min_value=pd.Timestamp.now().date(),
                    key="popup_delivery",
                    help="Select expected delivery date"
                )
                
                special_instructions = st.text_area(
                    "Special Instructions:",
                    placeholder="Any special requirements or notes for this order...",
                    key="popup_instructions",
                    help="Optional special instructions for the vendor"
                )
                
                # Form submission buttons
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    if st.form_submit_button("✅ Place Order", type="primary"):
                        # Get the current selected row data for order processing
                        if store_id and product_id:
                            current_selected_data = order_data[
                                (order_data['Store ID'] == store_id) & 
                                (order_data['Product ID'] == product_id)
                            ]
                            
                            if len(current_selected_data) > 0:
                                row_data = current_selected_data.iloc[0]
                                # Process the order
                                self._process_order(row_data.to_dict(), order_quantity, selected_vendor, delivery_date, special_instructions)
                                st.success(f"✅ Order placed successfully for {order_quantity} units of {product_id} from {selected_vendor}")
                                # Reset popup state
                                st.session_state['show_order_popup'] = False
                                st.session_state['order_data'] = None
                                st.rerun()
                            else:
                                st.error("❌ Please select valid Store ID and Product ID")
                        else:
                            st.error("❌ Please select both Store ID and Product ID")
                
                with col2:
                    if st.form_submit_button("❌ Cancel"):
                        st.session_state['show_order_popup'] = False
                        st.session_state['order_data'] = None
                        st.rerun()
                
                with col3:
                    if st.form_submit_button("📝 Save as Draft"):
                        st.info("📝 Order saved as draft (not yet submitted)")
                        st.session_state['show_order_popup'] = False
                        st.session_state['order_data'] = None
                        st.rerun()
        
        # Close button outside the form
        if st.button("❌ Close", key="close_popup"):
            st.session_state['show_order_popup'] = False
            st.session_state['order_data'] = None
            st.rerun()

    def _process_order(self, order_data, quantity, vendor, delivery_date, special_instructions):
        """Process the submitted order"""
        # Here you would typically:
        # 1. Save order to database
        # 2. Send notification to vendor
        # 3. Update inventory planning
        # 4. Log order history
        
        # For now, we'll just log the order details
        order_summary = {
            'timestamp': pd.Timestamp.now(),
            'store_id': order_data.get('Store ID'),
            'product_id': order_data.get('Product ID'),
            'category': order_data.get('Category'),
            'quantity': quantity,
            'vendor': vendor,
            'delivery_date': delivery_date,
            'special_instructions': special_instructions,
            'current_inventory': order_data.get('Inventory Level'),
            'unit_price': order_data.get('Price')
        }
        
        # Store in session state for demonstration (in real app, save to database)
        if 'order_history' not in st.session_state:
            st.session_state['order_history'] = []
        
        st.session_state['order_history'].append(order_summary)
        
        # You could also add this to a success message or notification system
        st.balloons()

    def _display_inventory_detail_tab(self, data):
        """Display inventory detail tab with charts and analysis"""
        st.subheader("📦 Product-Level Inventory Analysis")
        
        if 'Product ID' in data.columns and 'Category' in data.columns:
            # Top products by inventory
            top_products = data[['Product ID', 'Category', 'Inventory Level']].drop_duplicates(subset=['Product ID', 'Category'])
            top_products = top_products.nlargest(20, 'Inventory Level')
            
            fig = px.bar(top_products, x='Product ID', y='Inventory Level', 
                        color='Category', title='Top 20 Products by Inventory Level')
            
            fig.update_traces(
                texttemplate='%{text}', 
                textposition='outside',
                text=[self._format_number_for_display(y) for y in top_products['Inventory Level']]
            )
            
            fig.update_layout(
                title_x=0.3,
                title_font_size=16,
                title_font_color="black",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True, key="top_products_inventory_chart")
            
            # Low stock products
            low_stock_products = data[
                data['Inventory Level'] < self.reorder_point
            ][['Product ID', 'Category', 'Inventory Level']].drop_duplicates(subset=['Product ID', 'Category'])
            
            if len(low_stock_products) > 0:
                fig = px.bar(low_stock_products, x='Product ID', y='Inventory Level', 
                            color='Category', title=f'Low Stock Products (Below Reorder Point: {self.reorder_point})')
                
                fig.update_traces(
                    texttemplate='%{text}', 
                    textposition='outside',
                    text=[self._format_number_for_display(y) for y in low_stock_products['Inventory Level']]
                )
                
                fig.update_layout(
                    title_x=0.3,
                    title_font_size=16,
                    title_font_color="black",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True, key="low_stock_products_chart")
            else:
                st.info(f"All products are above the reorder point ({self.reorder_point})")
        
        # Detailed inventory table
        st.subheader("📋 Detailed Store & Product Inventory")
        if 'Store ID' in data.columns and 'Product ID' in data.columns:
            detailed_inventory = data[['Store ID', 'Product ID', 'Category', 'Inventory Level', 'Units Sold', 'Price']].drop_duplicates(subset=['Store ID', 'Product ID', 'Category'])
            
            detailed_inventory['Status'] = detailed_inventory['Inventory Level'].apply(
                lambda x: '🟢 Good' if x >= self.reorder_point else '🔴 Low Stock' if x > 0 else '⚫ Out of Stock'
            )
            
            self._display_inventory_table_with_orders(detailed_inventory)
        else:
            st.warning("Store ID or Product ID columns not available for detailed analysis")

    def _display_orders_in_transit_tab(self, selected_store):
        """Display orders in transit tab with order management"""
        st.subheader("🚚 Orders in Transit")
        
        # Load orders in transit data
        orders_data = self._load_orders_in_transit()
        
        if orders_data is not None and len(orders_data) > 0:
            # Filter orders by selected store if specified
            if selected_store and selected_store != 'All Stores':
                store_orders = orders_data[orders_data['Store ID'] == selected_store]
            else:
                store_orders = orders_data
            
            if len(store_orders) > 0:
                # Display orders table
                st.dataframe(store_orders, use_container_width=True, hide_index=True)
                
                # Place Order button below the table (same functionality as Inventory Detail tab)
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("📦 Place Order", type="primary", key="place_order_transit_btn", use_container_width=True):
                        st.session_state['show_order_popup'] = True
                        st.session_state['order_data'] = store_orders
                        st.rerun()
                
                # Display order popup if triggered
                if st.session_state.get('show_order_popup', False):
                    self._show_order_popup()
            else:
                st.info(f"No orders in transit found for Store: {selected_store}")
        else:
            st.info("No orders in transit found. Click 'Place Order' to create your first order.")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("📦 Place Order", type="primary", key="place_order_first_btn", use_container_width=True):
                    st.session_state['show_order_popup'] = True
                    st.session_state['order_data'] = pd.DataFrame()  # Empty dataframe for new orders
                    st.rerun()

    def _load_orders_in_transit(self):
        """Load orders in transit data from CSV file"""
        try:
            orders_file = "orders_in_transit.csv"
            if os.path.exists(orders_file):
                return pd.read_csv(orders_file)
            else:
                st.warning("Orders in transit file not found. Please create the file first.")
                return None
        except Exception as e:
            st.error(f"Error loading orders in transit data: {str(e)}")
            return None

    def display_inventory_analysis(self):
        """Display inventory analysis with two main tabs"""
        
        # Create tabs for different inventory views
        tab1, tab2 = st.tabs(["📈 Overall Inventory", "🏪 Store & Product Level Inventory"])
        
        with tab1:
            self._display_overall_inventory_analysis(self.filtered_data)
        
        with tab2:            
            self._display_store_product_inventory_analysis(self.filtered_data)

    def run(self):
        st.title("📊 Real-Time Inventory Optimization Dashboard")
        st.markdown("---")
        
        # Setup sidebar first
        self.setup_sidebar()
        
        # Load data and check if successful
        if not self.load_data():
            st.warning("⚠️ Please ensure 'retail_store_inventory.csv' exists in the current directory or upload a CSV file.")
            st.info("💡 You can also use the file uploader in the sidebar to upload your CSV file.")
            return
        
        # Create tabs only if data is loaded
        tab1, tab2, tab3 = st.tabs(["📊 Overview", "📦 Store Inventory Analysis", "💰 Sales Analysis"])
        
        with tab1:
            # Display overview dashboard
            self.display_overview()
        
        with tab2:
            # Display inventory dashboard
            self.display_inventory_analysis()
        
        with tab3:
            # Display sales analysis
            self.display_sales_analysis()

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.run() 