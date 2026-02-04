import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

# Page config
st.set_page_config(page_title="Pendle Maturity Optimizer", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for dark theme
st.markdown("""
<style>
    .stApp {
        background-color: #111827;
    }
    .stMarkdown h1 {
        color: #ffffff;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .stMarkdown h2 {
        color: #ffffff;
        font-size: 1.8rem;
        margin-top: 2rem;
    }
    .stMarkdown p {
        color: #9ca3af;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# Tier configuration
TIER_THRESHOLDS = {
    1: 500_000_000,   # > $500M
    2: 100_000_000,   # $100M - $500M
    3: 10_000_000,    # $10M - $100M
    4: 0              # < $10M
}

TIER_COLORS = {
    1: '#8b5cf6',  # Purple
    2: '#06b6d4',  # Cyan
    3: '#10b981',  # Green
    4: '#f59e0b'   # Orange
}

def get_tier(tvl):
    if tvl >= TIER_THRESHOLDS[1]:
        return 1
    elif tvl >= TIER_THRESHOLDS[2]:
        return 2
    elif tvl >= TIER_THRESHOLDS[3]:
        return 3
    else:
        return 4

@st.cache_data(ttl=300)
def fetch_markets():
    """Fetch active markets from Pendle API"""
    try:
        response = requests.get('https://api-v2.pendle.finance/core/v1/markets/all?isActive=true')
        data = response.json()
        return data.get('markets', [])
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def main():
    st.title("🔄 Pendle Maturity Date Optimizer")
    st.markdown("Visualize TVL distribution and optimize pool deployment timing")
    
    # Initialize session state
    if 'simulated_pools' not in st.session_state:
        st.session_state.simulated_pools = []
    if 'relaunch_selections' not in st.session_state:
        st.session_state.relaunch_selections = {}
    
    # Fetch market data
    markets = fetch_markets()
    
    if not markets:
        st.error("Failed to load market data")
        return
    
    # Convert to DataFrame - strip timezone for consistency
    df = pd.DataFrame([{
        'name': m['name'],
        'address': m['address'],
        'expiry': pd.to_datetime(m['expiry']).tz_localize(None),
        'tvl': m['details'].get('totalTvl', 0),
        'chainId': m['chainId'],
        'is_relaunch': False
    } for m in markets])
    
    df['tier'] = df['tvl'].apply(get_tier)
    df['expiry_date'] = df['expiry'].dt.date
    
    # Add simulated pools
    if st.session_state.simulated_pools:
        simulated_df = pd.DataFrame(st.session_state.simulated_pools)
        # Convert date to datetime (timezone-naive)
        simulated_df['expiry'] = pd.to_datetime(simulated_df['expiry_date'])
        df = pd.concat([df, simulated_df], ignore_index=True)
    
    # New Pool Simulation Section
    st.markdown("---")
    st.header("➕ Simulate New Pool Launch")
    
    with st.expander("Add New Pool", expanded=False):
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        
        with col1:
            new_pool_name = st.text_input("Pool Name", placeholder="e.g., stETH, USDC", key="new_pool_name")
        
        with col2:
            new_pool_date = st.date_input(
                "Maturity Date",
                value=datetime.now() + timedelta(days=180),
                key="new_pool_date"
            )
        
        with col3:
            new_pool_tier = st.selectbox(
                "Tier",
                options=[1, 2, 3, 4],
                format_func=lambda x: f"Tier {x}",
                index=2,  # Default to Tier 3
                key="new_pool_tier"
            )
        
        with col4:
            new_pool_tvl = st.number_input(
                "Expected TVL ($M)",
                min_value=0.0,
                value=10.0,
                step=1.0,
                key="new_pool_tvl"
            )
        
        if st.button("Add to Simulation", type="primary", key="add_new_pool"):
            if new_pool_name.strip():
                st.session_state.simulated_pools.append({
                    'name': new_pool_name,
                    'address': f"simulated_{len(st.session_state.simulated_pools)}",
                    'expiry_date': new_pool_date,
                    'tvl': new_pool_tvl * 1_000_000,  # Convert M to actual value
                    'tier': new_pool_tier,
                    'chainId': 'Simulated',
                    'is_relaunch': False
                })
                st.success(f"Added {new_pool_name} to simulation!")
                st.rerun()
            else:
                st.error("Please enter a pool name")
    
    # Expiring pools section
    st.markdown("---")
    st.header("⚠️ Pools Expiring Soon (>$1M TVL, Next 3 Weeks)")
    
    now = pd.Timestamp(datetime.now())
    three_weeks = now + pd.Timedelta(days=21)
    
    expiring = df[
        (df['tvl'] > 1_000_000) & 
        (df['expiry'] <= three_weeks) & 
        (df['expiry'] > now)
    ].sort_values('expiry')
    
    if len(expiring) > 0:
        for idx, pool in expiring.iterrows():
            days_left = (pool['expiry'] - now).days
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                tier_color = TIER_COLORS[pool['tier']]
                st.markdown(f"""
                <div style='background-color: #1f2937; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                    <h3 style='color: white; margin: 0;'>
                        {pool['name']} 
                        <span style='background-color: {tier_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; margin-left: 0.5rem;'>
                            Tier {pool['tier']}
                        </span>
                    </h3>
                    <p style='color: #9ca3af; margin: 0.5rem 0 0 0;'>
                        Expires: {pool['expiry'].strftime('%Y-%m-%d')} • 
                        <span style='color: #ef4444; font-weight: bold;'>{days_left} days left</span> • 
                        TVL: ${pool['tvl']/1_000_000:.2f}M • 
                        Chain: {pool['chainId']}
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                relaunch = st.checkbox("Relaunch?", key=f"relaunch_{pool['address']}")
            
            with col3:
                if relaunch:
                    if st.button("Configure", key=f"config_{pool['address']}"):
                        st.session_state.relaunch_selections[pool['address']] = pool.to_dict()
            
            # Show relaunch form if selected
            if pool['address'] in st.session_state.relaunch_selections:
                with st.expander(f"Configure Relaunch for {pool['name']}", expanded=True):
                    rcol1, rcol2, rcol3 = st.columns(3)
                    
                    with rcol1:
                        new_date = st.date_input(
                            "New Maturity Date",
                            value=datetime.now().date() + timedelta(days=180),
                            key=f"date_{pool['address']}"
                        )
                    
                    with rcol2:
                        new_tier = st.selectbox(
                            "Tier",
                            options=[1, 2, 3, 4],
                            format_func=lambda x: f"Tier {x}",
                            index=1,
                            key=f"tier_{pool['address']}"
                        )
                    
                    with rcol3:
                        st.write("")
                        st.write("")
                        if st.button("Add to Simulation", key=f"add_{pool['address']}", type="primary"):
                            st.session_state.simulated_pools.append({
                                'name': f"{pool['name']} (Relaunched)",
                                'address': f"{pool['address']}_relaunch",
                                'expiry_date': new_date,
                                'tvl': pool['tvl'],
                                'tier': new_tier,
                                'chainId': pool['chainId'],
                                'is_relaunch': True
                            })
                            del st.session_state.relaunch_selections[pool['address']]
                            st.rerun()
    else:
        st.info("No pools expiring in the next 3 weeks")
    
    # Simulated pools display
    if st.session_state.simulated_pools:
        st.markdown("---")
        st.header("📊 Simulated Pools")
        
        for i, pool in enumerate(st.session_state.simulated_pools):
            col1, col2 = st.columns([5, 1])
            
            with col1:
                tier_color = TIER_COLORS[pool['tier']]
                badge = ""
                if pool.get('is_relaunch'):
                    badge = " <span style='background-color: #3b82f6; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;'>Relaunch</span>"
                elif pool.get('chainId') == 'Simulated':
                    badge = " <span style='background-color: #10b981; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;'>New</span>"
                
                st.markdown(f"""
                <div style='background-color: #374151; padding: 0.75rem; border-radius: 0.5rem; margin-bottom: 0.5rem;'>
                    <span style='color: white; font-weight: 600;'>{pool['name']}</span>
                    {badge}
                    <span style='color: #9ca3af; margin-left: 1rem;'>{pool['expiry_date']}</span>
                    <span style='color: white; margin-left: 1rem; font-weight: 600;'>${pool['tvl']/1_000_000:.2f}M</span>
                    <span style='background-color: {tier_color}; color: white; padding: 0.2rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; margin-left: 0.5rem;'>
                        Tier {pool['tier']}
                    </span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if st.button("Remove", key=f"remove_{i}"):
                    st.session_state.simulated_pools.pop(i)
                    st.rerun()
    
    # Aggregate data by date
    agg_data = df.groupby('expiry_date').agg({
        'tvl': 'sum',
        'name': list
    }).reset_index()
    
    # Calculate tier TVL for each date
    for tier in [1, 2, 3, 4]:
        tier_data = df[df['tier'] == tier].groupby('expiry_date')['tvl'].sum()
        agg_data[f'tier{tier}'] = agg_data['expiry_date'].map(tier_data).fillna(0)
    
    agg_data = agg_data.sort_values('expiry_date')
    
    # Chart 1: TVL Distribution by Maturity Date (Stacked by Tier)
    st.markdown("---")
    st.header("📊 TVL Distribution by Maturity Date")
    
    fig1 = go.Figure()
    
    # Convert dates to strings for plotting
    dates_str = agg_data['expiry_date'].astype(str).tolist()
    
    fig1.add_trace(go.Bar(
        name='Tier 1 (>$500M)',
        x=dates_str,
        y=agg_data['tier1'].tolist(),
        marker=dict(color=TIER_COLORS[1], line=dict(color='#1f2937', width=0.5))
    ))
    
    fig1.add_trace(go.Bar(
        name='Tier 2 ($100M-$500M)',
        x=dates_str,
        y=agg_data['tier2'].tolist(),
        marker=dict(color=TIER_COLORS[2], line=dict(color='#1f2937', width=0.5))
    ))
    
    fig1.add_trace(go.Bar(
        name='Tier 3 ($10M-$100M)',
        x=dates_str,
        y=agg_data['tier3'].tolist(),
        marker=dict(color=TIER_COLORS[3], line=dict(color='#1f2937', width=0.5))
    ))
    
    fig1.add_trace(go.Bar(
        name='Tier 4 (<$10M)',
        x=dates_str,
        y=agg_data['tier4'].tolist(),
        marker=dict(color=TIER_COLORS[4], line=dict(color='#1f2937', width=0.5))
    ))
    
    fig1.update_layout(
        barmode='stack',
        height=700,
        plot_bgcolor='#1f2937',
        paper_bgcolor='#1f2937',
        font=dict(color='#e5e7eb', size=12),
        xaxis=dict(
            title='Maturity Date',
            gridcolor='#4b5563',
            tickangle=-45
        ),
        yaxis=dict(
            title='Total TVL',
            gridcolor='#4b5563',
            tickformat='$,.0f'
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='#1f2937',
            font_size=12,
            font_color='white',
            bordercolor='#8b5cf6'
        )
    )
    
    st.plotly_chart(fig1, use_container_width=True)
    
    # Chart 2: Individual Pools by Maturity Date
    st.markdown("---")
    st.header("📊 Individual Pools by Maturity Date")
    st.markdown("*Hover over any bar to see all pools expiring on that date*")
    
    fig2 = go.Figure()
    
    # Create hover text with pool details
    hover_texts = []
    for idx, row in agg_data.iterrows():
        date = row['expiry_date']
        pools_on_date = df[df['expiry_date'] == date].sort_values('tvl', ascending=False)
        
        if len(pools_on_date) == 0:
            hover_text = f"<b>{date}</b><br>No pools available"
        else:
            # Build HTML tooltip
            lines = [
                f"<b>{date}</b>",
                f"<b>Total TVL: ${row['tvl']/1_000_000:.2f}M</b>",
                f"{len(pools_on_date)} pool{'s' if len(pools_on_date) > 1 else ''}",
                "━━━━━━━━━━━━━━━━"
            ]
            
            # Add each pool
            for _, pool in pools_on_date.iterrows():
                tier_name = f"T{pool['tier']}"
                lines.append(f"<b>{pool['name']}</b> ({tier_name}): ${pool['tvl']/1_000_000:.2f}M")
            
            hover_text = '<br>'.join(lines)
        
        hover_texts.append(hover_text)
    
    fig2.add_trace(go.Bar(
        x=dates_str,
        y=agg_data['tvl'].tolist(),
        marker=dict(
            color='#8b5cf6',
            line=dict(color='#6d28d9', width=1.5)
        ),
        hovertext=hover_texts,
        hovertemplate='%{hovertext}<extra></extra>'
    ))
    
    fig2.update_layout(
        height=700,
        plot_bgcolor='#1f2937',
        paper_bgcolor='#1f2937',
        font=dict(color='#e5e7eb', size=12),
        xaxis=dict(
            title='Maturity Date',
            gridcolor='#4b5563',
            tickangle=-45
        ),
        yaxis=dict(
            title='Total TVL',
            gridcolor='#4b5563',
            tickformat='$,.0f'
        ),
        showlegend=False,
        hovermode='closest',
        hoverlabel=dict(
            bgcolor='#1f2937',
            font_size=12,
            font_color='white',
            bordercolor='#8b5cf6',
            align='left'
        )
    )
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # Summary stats
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        original_markets = len(df[~df['is_relaunch']]) if 'is_relaunch' in df.columns else len(df)
        st.metric("Total Markets", original_markets)
    
    with col2:
        st.metric("Maturity Dates", len(agg_data))
    
    with col3:
        st.metric("Expiring Soon", len(expiring), delta=None if len(expiring) == 0 else "⚠️")
    
    with col4:
        total_tvl = df['tvl'].sum() / 1_000_000_000
        st.metric("Total TVL", f"${total_tvl:.2f}B")
    
    # Date Selector and Pool Details Table
    st.markdown("---")
    st.header("📅 Pool Details by Maturity Date")
    
    # Get unique dates sorted
    available_dates = sorted(df['expiry_date'].unique())
    
    if len(available_dates) > 0:
        col1, col2 = st.columns([2, 5])
        
        with col1:
            selected_date = st.selectbox(
                "Select Maturity Date",
                options=available_dates,
                format_func=lambda x: f"{x} ({len(df[df['expiry_date'] == x])} pools)",
                key="date_selector"
            )
        
        with col2:
            pools_on_date = df[df['expiry_date'] == selected_date].sort_values('tvl', ascending=False)
            total_tvl_date = pools_on_date['tvl'].sum()
            st.metric(
                f"Total TVL on {selected_date}", 
                f"${total_tvl_date/1_000_000:.2f}M",
                f"{len(pools_on_date)} pools"
            )
        
        # Display table
        if len(pools_on_date) > 0:
            # Prepare data for display
            table_data = []
            for idx, pool in pools_on_date.iterrows():
                table_data.append({
                    'Pool': pool['name'],
                    'Tier': f"Tier {pool['tier']}",
                    'TVL ($M)': f"${pool['tvl']/1_000_000:.2f}M",
                    'Chain': pool['chainId'],
                    'Type': 'Relaunch' if pool.get('is_relaunch') else ('New' if pool.get('chainId') == 'Simulated' else 'Active')
                })
            
            table_df = pd.DataFrame(table_data)
            
            # Style the dataframe
            st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True,
                height=min(400, len(table_df) * 35 + 38)  # Dynamic height based on rows
            )
        else:
            st.info("No pools maturing on this date")
    else:
        st.info("No maturity dates available")

if __name__ == "__main__":
    main()
