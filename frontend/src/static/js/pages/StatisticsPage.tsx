import React, { useState, useEffect, useContext } from 'react';
import { Page } from './Page';
import { MediaStatsChart, MediaTrendsChart } from '../components/charts';
import { ApiUrlContext } from '../utils/contexts';
import { useUser } from '../utils/hooks/';
import { csrfToken } from '../utils/helpers';
import axios from 'axios';
import '../../css/dashboard.scss';

interface StatisticsPageProps {
  id?: string;
}

interface AnalyticsData {
  media_analytics: Array<{
    title: string;
    views: number;
  }>;
  total_media_count: number;
}

interface PlaylistAnalyticsData {
  playlist_analytics: Array<{
    playlist_title: string;
    total_views: number;
  }>;
  total_playlists_count: number;
}

interface UserAnalyticsData {
  total_users: number;
}

export const StatisticsPage: React.FC<StatisticsPageProps> = ({
  id = 'statistics',
}) => {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [playlistAnalyticsData, setPlaylistAnalyticsData] = useState<PlaylistAnalyticsData | null>(null);
  const [userAnalyticsData, setUserAnalyticsData] = useState<UserAnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const apiUrl = useContext(ApiUrlContext);
  const { isAnonymous, userCan } = useUser();

  // Check if user has permission to view analytics
  const hasAnalyticsPermission = !isAnonymous && (userCan.manageMedia || userCan.manageUsers);

  useEffect(() => {
    if (!hasAnalyticsPermission) {
      setError('You do not have permission to view analytics data. This feature is available to administrators, managers, and editors only.');
      setLoading(false);
      return;
    }

    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const response = await axios.get('/api/v1/media/analytics', {
          withCredentials: true,
          headers: {
            'X-CSRFToken': csrfToken(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          timeout: 10000,
        });

        if (response.data) {
          setAnalyticsData(response.data);
        }
      } catch (err) {
        console.error('Error fetching analytics data:', err);
        if (axios.isAxiosError(err)) {
          if (err.response?.status === 401) {
            setError('Authentication required. Please log in to view analytics.');
          } else if (err.response?.status === 403) {
            setError('Access forbidden. You do not have permission to view analytics.');
          } else if (err.response?.status === 404) {
            setError('Analytics endpoint not found.');
          } else {
            setError(`Failed to fetch analytics data: ${err.message}`);
          }
        } else {
          setError('An unexpected error occurred while fetching analytics data.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [hasAnalyticsPermission]);

  useEffect(() => {
    if (!hasAnalyticsPermission) {
      return;
    }

    const fetchPlaylistAnalytics = async () => {
      try {
        const response = await axios.get('/api/v1/playlists/analytics', {
          withCredentials: true,
          headers: {
            'X-CSRFToken': csrfToken(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          timeout: 10000,
        });

        if (response.data) {
          setPlaylistAnalyticsData(response.data);
        }
      } catch (err) {
        console.error('Error fetching playlist analytics data:', err);
        // Don't set error here as media analytics is primary
      }
    };

    fetchPlaylistAnalytics();
  }, [hasAnalyticsPermission]);

  useEffect(() => {
    if (!hasAnalyticsPermission) {
      return;
    }

    const fetchUserAnalytics = async () => {
      try {
        const response = await axios.get('/api/v1/users/analytics', {
          withCredentials: true,
          headers: {
            'X-CSRFToken': csrfToken(),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          timeout: 10000,
        });

        if (response.data) {
          setUserAnalyticsData(response.data);
        }
      } catch (err) {
        console.error('Error fetching user analytics data:', err);
        // Don't set error here as media analytics is primary
      }
    };

    fetchUserAnalytics();
  }, [hasAnalyticsPermission]);

  if (!hasAnalyticsPermission) {
    return (
      <Page id={id}>
        <div className="statistics-page">
          <div className="error-container">
            <h2>Access Restricted</h2>
            <p>{error}</p>
            <p>Statistics and analytics are available to:</p>
            <ul>
              <li>System administrators</li>
              <li>MediaCMS managers</li>
              <li>MediaCMS editors</li>
            </ul>
          </div>
        </div>
      </Page>
    );
  }

  if (loading) {
    return (
      <Page id={id}>
        <div className="statistics-page">
          <div className="loading-container">
            <p>Loading analytics data...</p>
          </div>
        </div>
      </Page>
    );
  }

  if (error) {
    return (
      <Page id={id}>
        <div className="statistics-page">
          <div className="error-container">
            <h2>Error Loading Analytics</h2>
            <p>{error}</p>
          </div>
        </div>
      </Page>
    );
  }

  return (
    <Page id={id}>
      <div className="statistics-page">
        <div className="dashboard-container">
          {/* Media Analytics Section */}
          {analyticsData && (
            <div className="analytics-section">
              <div className="section-header">
                <h2>📊 Media Analytics</h2>
                <div className="stats-summary">
                  <div className="stat-item">
                    <h3 className="stat-label">Total Media:</h3>
                    <span className="stat-value">{analyticsData.total_media_count.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              
              <div className="chart-row">
                <div className="chart-container">
                  <div className="chart-wrapper">
                    <h3 className="chart-title">Top Media by Views</h3>
                    <MediaStatsChart
                      title="Top Media by Views"
                      width="100%"
                      height="400px"
                      horizontal={false}
                      media_analytics={analyticsData.media_analytics}
                    />
                  </div>
                </div>
                
                <div className="chart-container">
                  <div className="chart-wrapper">
                    <h3 className="chart-title">Media Views</h3>
                    <MediaStatsChart
                      title="Media Views (Horizontal)"
                      width="100%"
                      height="400px"
                      horizontal={true}
                      media_analytics={analyticsData.media_analytics}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Playlist Analytics Section */}
          {playlistAnalyticsData && (
            <div className="analytics-section">
              <div className="section-header">
                <h2>📋 Playlist Analytics</h2>
                <div className="stats-summary">
                  <div className="stat-item">
                    <h3 className="stat-label">Total Playlists:</h3>
                    <span className="stat-value">{playlistAnalyticsData.total_playlists_count.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              
              <div className="chart-container">
                <div className="chart-wrapper">
                  <MediaStatsChart
                    title="Top Playlists by Total Views"
                    width="100%"
                    height="400px"
                    horizontal={false}
                    media_analytics={playlistAnalyticsData.playlist_analytics.map(p => ({
                      title: p.playlist_title,
                      views: p.total_views
                    }))}
                  />
                </div>
              </div>
            </div>
          )}

          {/* User Analytics Section */}
          {userAnalyticsData && (
            <div className="analytics-section">
              <div className="section-header">
                <h2>👥 User Analytics</h2>
                <div className="stats-summary">
                  <div className="stat-item">
                    <h3 className="stat-label">Total Users:</h3>
                    <span className="stat-value">{userAnalyticsData.total_users.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}; 