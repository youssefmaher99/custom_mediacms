import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface MediaAnalytics {
  title?: string;
  views?: number;
  playlist_title?: string; 
  total_views?: number;
}

interface MediaStatsChartProps {
  title?: string;
  width?: string;
  height?: string;
  horizontal?: boolean;
  media_analytics: MediaAnalytics[];
}

export const MediaStatsChart: React.FC<MediaStatsChartProps> = ({
  title = 'Media Analytics',
  width = '100%',
  height = '400px',
  horizontal = false,
  // make it dynamic from the props
  media_analytics,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    // Initialize the echarts instance
    const myChart = echarts.init(chartRef.current);

    // Prepare data for bar chart
    const mediaTitles = media_analytics.map(item => item.title);
    const viewCounts = media_analytics.map(item => item.views);

    // Chart configuration
    const option = {
      title: {
        text: title,
        left: 'center',
        textStyle: {
          color: '#333',
          fontSize: 18,
          fontWeight: 'bold',
        },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow',
        },
        formatter: function(params: any) {
          return `${params[0].name}<br/>Views: ${params[0].value}`;
        },
      },
      grid: {
        left: horizontal ? '15%' : '3%',
        right: '4%',
        bottom: horizontal ? '10%' : '15%',
        containLabel: true,
      },
      xAxis: {
        type: horizontal ? 'value' : 'category',
        data: horizontal ? undefined : mediaTitles,
        name: horizontal ? 'Views' : undefined,
        nameTextStyle: horizontal ? {
          color: '#666',
        } : undefined,
        axisLabel: horizontal ? {
          textStyle: {
            color: '#666',
          },
        } : {
          rotate: 45,
          interval: 0,
          textStyle: {
            color: '#666',
            fontSize: 10,
          },
          formatter: function(value: string) {
            // Truncate long titles
            return value.length > 15 ? value.substring(0, 15) + '...' : value;
          },
        },
        axisTick: horizontal ? undefined : {
          alignWithLabel: true,
        },
        splitLine: horizontal ? {
          lineStyle: {
            color: '#e6e6e6',
          },
        } : undefined,
      },
      yAxis: {
        type: horizontal ? 'category' : 'value',
        data: horizontal ? mediaTitles : undefined,
        name: horizontal ? undefined : 'Views',
        nameTextStyle: horizontal ? undefined : {
          color: '#666',
        },
        axisLabel: horizontal ? {
          textStyle: {
            color: '#666',
            fontSize: 10,
          },
          formatter: function(value: string) {
            // Truncate long titles for horizontal chart
            return value.length > 20 ? value.substring(0, 20) + '...' : value;
          },
        } : {
          textStyle: {
            color: '#666',
          },
        },
        splitLine: horizontal ? undefined : {
          lineStyle: {
            color: '#e6e6e6',
          },
        },
      },
      series: [
        {
          name: 'Views',
          type: 'bar',
          data: viewCounts,
          itemStyle: {
            color: '#5470c6',
            borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
          },
          emphasis: {
            itemStyle: {
              color: '#3b5998',
            },
          },
          label: {
            show: true,
            position: horizontal ? 'right' : 'top',
            textStyle: {
              color: '#333',
              fontSize: 10,
            },
          },
        },
      ],
    };

    // Use the configuration item and data specified to show the chart
    myChart.setOption(option);

    // Handle window resize
    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);

    // Cleanup function
    return () => {
      window.removeEventListener('resize', handleResize);
      myChart.dispose();
    };
  }, [title, media_analytics, horizontal]);

  // Calculate dynamic height for horizontal charts based on number of items
  const getChartHeight = () => {
    if (horizontal) {
      // Each bar needs approximately 40px height, plus padding for title and margins
      const barHeight = 40;
      const titleHeight = 60;
      const margins = 40;
      return Math.max(300, media_analytics.length * barHeight + titleHeight + margins);
    }
    return height;
  };

  return (
    <div
      style={{
        width,
        maxHeight: horizontal ? '500px' : undefined,
        overflowY: horizontal ? 'auto' : 'visible',
        margin: '20px 0',
        border: horizontal ? '1px solid #e6e6e6' : 'none',
        borderRadius: horizontal ? '4px' : '0',
      }}
    >
      <div
        ref={chartRef}
        style={{
          width: '100%',
          height: getChartHeight(),
        }}
      />
    </div>
  );
}; 