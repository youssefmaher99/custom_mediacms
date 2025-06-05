import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface MediaTrendsChartProps {
  title?: string;
  width?: string;
  height?: string;
}

export const MediaTrendsChart: React.FC<MediaTrendsChartProps> = ({
  title = 'Media Upload Trends',
  width = '100%',
  height = '300px',
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current);

    // Sample data for the last 7 days
    const dates = [];
    const uploads = [];
    
    for (let i = 6; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      dates.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
      uploads.push(Math.floor(Math.random() * 50) + 10); // Random data for demo
    }

    const option = {
      title: {
        text: title,
        left: 'center',
        textStyle: {
          color: '#333',
          fontSize: 16,
          fontWeight: 'bold',
        },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985',
          },
        },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: [
        {
          type: 'category',
          boundaryGap: false,
          data: dates,
          axisLabel: {
            color: '#666',
          },
          axisLine: {
            lineStyle: {
              color: '#ddd',
            },
          },
        },
      ],
      yAxis: [
        {
          type: 'value',
          axisLabel: {
            color: '#666',
          },
          axisLine: {
            lineStyle: {
              color: '#ddd',
            },
          },
          splitLine: {
            lineStyle: {
              color: '#f5f5f5',
            },
          },
        },
      ],
      series: [
        {
          name: 'Uploads',
          type: 'line',
          stack: 'Total',
          smooth: true,
          areaStyle: {
            opacity: 0.3,
          },
          emphasis: {
            focus: 'series',
          },
          data: uploads,
          itemStyle: {
            color: '#5470c6',
          },
          lineStyle: {
            width: 3,
          },
        },
      ],
    };

    myChart.setOption(option);

    return () => {
      myChart.dispose();
    };
  }, [title]);

  return (
    <div
      ref={chartRef}
      style={{
        width,
        height,
        margin: '20px 0',
      }}
    />
  );
}; 