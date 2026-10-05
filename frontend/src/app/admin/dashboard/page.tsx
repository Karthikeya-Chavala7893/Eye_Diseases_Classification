'use client';

/**
 * app/admin/dashboard/page.tsx
 * ───────────────────────────
 * Next-Generation Clinical Admin Dashboard.
 * Displays ALL 8 clinical retinal conditions tracked across the platform:
 *   1. Healthy Retina (Normal)
 *   2. Diabetic Signs / Diabetic Retinopathy (Mild, Moderate, Severe, Proliferative)
 *   3. Glaucoma
 *   4. Cataract
 *   5. Macular Degeneration (AMD)
 *   6. Hypertensive Retinopathy
 *   7. Myopia (Pathological Myopia)
 *   8. Other Retinal Findings
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Navbar, type NavLink } from '@/components/Navbar';
import { MinimalFooter } from '@/components/Footer';
import { useAuth } from '@/hooks/useAuth';
import {
  fetchAdminStats,
  fetchAdminUsers,
  fetchAdminScans,
  verifyAdmin,
  promoteToAdmin,
} from '@/lib/api';
import { getConfidenceLevel } from '@/components/ConfidenceBar';
import type { AdminStatsData, AdminUser, AdminScan } from '@/types/admin';

const NAV_LINKS: NavLink[] = [
  { href: '/', label: 'Home' },
  { href: '/screening', label: 'AI Screening' },
  { href: '/admin/dashboard', label: 'Admin Cockpit', active: true },
];

type ActiveTab = 'overview' | 'scans' | 'users' | 'system';

// ── Complete 8 Clinical Monitored Conditions ────────────────────────────────

interface MonitoredConditionDef {
  id: string;
  name: string;
  shortName: string;
  icon: string;
  color: string;
  aliases: string[];
}

const MONITORED_DISEASES: MonitoredConditionDef[] = [
  {
    id: 'normal',
    name: 'Healthy Retina',
    shortName: 'Healthy Retina',
    icon: '✅',
    color: '#10B981',
    aliases: ['healthy', 'healthy retina', 'healthy_retina', 'no_dr', 'normal', 'no signs'],
  },
  {
    id: 'diabetes',
    name: 'Diabetic Signs / DR',
    shortName: 'Diabetic Signs',
    icon: '🩺',
    color: '#F59E0B',
    aliases: [
      'diabetes',
      'diabetic signs',
      'diabetic_retinopathy',
      'mild',
      'moderate',
      'severe',
      'proliferative_dr',
      'dr',
      'mild diabetic retinopathy',
      'moderate diabetic retinopathy',
      'severe diabetic retinopathy',
      'proliferative diabetic retinopathy',
    ],
  },
  {
    id: 'glaucoma',
    name: 'Glaucoma',
    shortName: 'Glaucoma',
    icon: '⚠️',
    color: '#8B5CF6',
    aliases: ['glaucoma', 'glaucoma detected'],
  },
  {
    id: 'cataract',
    name: 'Cataract',
    shortName: 'Cataract',
    icon: '🌫️',
    color: '#3B82F6',
    aliases: ['cataract', 'cataracts', 'cataract detected'],
  },
  {
    id: 'amd',
    name: 'Macular Degeneration (AMD)',
    shortName: 'AMD',
    icon: '🔴',
    color: '#EF4444',
    aliases: ['amd', 'amd – macular degeneration', 'macular degeneration', 'age_related_macular_degeneration'],
  },
  {
    id: 'hypertension',
    name: 'Hypertensive Retinopathy',
    shortName: 'Hypertension',
    icon: '🩸',
    color: '#DC2626',
    aliases: ['hypertension', 'hypertensive retinopathy'],
  },
  {
    id: 'myopia',
    name: 'Myopia (Pathological)',
    shortName: 'Myopia',
    icon: '👓',
    color: '#0EA5E9',
    aliases: ['myopia', 'myopia detected', 'nearsightedness', 'pathological_myopia'],
  },
  {
    id: 'other',
    name: 'Other Retinal Findings',
    shortName: 'Other Finding',
    icon: '🔍',
    color: '#6366F1',
    aliases: ['other', 'other finding detected', 'unknown', 'default', 'unclassified'],
  },
];

function matchCondition(rawLabel: string): MonitoredConditionDef {
  const norm = (rawLabel || '').toLowerCase().trim();
  for (const cond of MONITORED_DISEASES) {
    if (cond.id === norm || cond.name.toLowerCase() === norm || cond.shortName.toLowerCase() === norm) {
      return cond;
    }
    if (cond.aliases.some((alias) => norm === alias || norm.includes(alias))) {
      return cond;
    }
  }
  return {
    id: 'custom',
    name: rawLabel.replace(/_/g, ' '),
    shortName: rawLabel.replace(/_/g, ' '),
    icon: '🔬',
    color: '#0EA5E9',
    aliases: [],
  };
}

// ── Interactive SVG Donut Chart with All 8 Diseases ──────────────────────────

interface ChartItem {
  id: string;
  label: string;
  displayName: string;
  value: number;
  color: string;
  icon: string;
  percentage: number;
}

function ClinicalPathologyDonut({
  rawDistribution,
  title,
  subtitle,
  size = 200,
}: {
  rawDistribution: Record<string, number>;
  title: string;
  subtitle?: string;
  size?: number;
}): JSX.Element {
  const [hoveredItem, setHoveredItem] = useState<ChartItem | null>(null);

  // Aggregate raw counts into the 8 canonical clinical conditions
  const { allItems, activeSlices, totalScans } = useMemo(() => {
    const counts: Record<string, number> = {};
    MONITORED_DISEASES.forEach((d) => {
      counts[d.id] = 0;
    });

    let total = 0;
    Object.entries(rawDistribution).forEach(([rawLabel, count]) => {
      const matched = matchCondition(rawLabel);
      if (counts[matched.id] !== undefined) {
        counts[matched.id] += count;
      } else {
        counts[matched.id] = (counts[matched.id] || 0) + count;
      }
      total += count;
    });

    const fullList: ChartItem[] = MONITORED_DISEASES.map((cond) => {
      const val = counts[cond.id] || 0;
      const pct = total > 0 ? (val / total) * 100 : 0;
      return {
        id: cond.id,
        label: cond.id,
        displayName: cond.name,
        value: val,
        color: cond.color,
        icon: cond.icon,
        percentage: pct,
      };
    });

    // Sort: conditions with counts first (descending), then rest
    fullList.sort((a, b) => b.value - a.value);

    const active = fullList.filter((item) => item.value > 0);

    return {
      allItems: fullList,
      activeSlices: active,
      totalScans: total,
    };
  }, [rawDistribution]);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 12;
  let cumulativeAngle = -90;

  // Build paths for active slices
  const paths = activeSlices.map((slice) => {
    const angle = (slice.value / (totalScans || 1)) * 360;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + angle;
    cumulativeAngle = endAngle;

    const startRad = (Math.PI / 180) * startAngle;
    const endRad = (Math.PI / 180) * endAngle;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;
    const isHovered = hoveredItem?.id === slice.id;

    if (activeSlices.length === 1) {
      return (
        <circle
          key={slice.id}
          cx={cx}
          cy={cy}
          r={radius}
          fill={slice.color}
          stroke="var(--bg-primary, #ffffff)"
          strokeWidth="3"
          onMouseEnter={() => setHoveredItem(slice)}
          onMouseLeave={() => setHoveredItem(null)}
          style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
        />
      );
    }

    const d = [
      `M ${cx} ${cy}`,
      `L ${x1} ${y1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
      'Z',
    ].join(' ');

    return (
      <path
        key={slice.id}
        d={d}
        fill={slice.color}
        stroke="var(--bg-primary, #ffffff)"
        strokeWidth={isHovered ? '4' : '2'}
        opacity={hoveredItem && !isHovered ? 0.6 : 1}
        onMouseEnter={() => setHoveredItem(slice)}
        onMouseLeave={() => setHoveredItem(null)}
        style={{
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          transform: isHovered ? 'scale(1.03)' : 'scale(1)',
          transformOrigin: `${cx}px ${cy}px`,
        }}
      >
        <title>{`${slice.displayName}: ${slice.value} (${slice.percentage.toFixed(1)}%)`}</title>
      </path>
    );
  });

  return (
    <div className="admin-chart-glass-panel">
      <div className="admin-panel-title-row">
        <div className="admin-panel-title">
          <span>{title}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="admin-panel-badge" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10B981' }}>
            8/8 Diseases Monitored
          </span>
          {subtitle && <span className="admin-panel-badge">{subtitle}</span>}
        </div>
      </div>

      <div className="admin-donut-layout">
        {/* SVG Donut */}
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
          <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            style={{ display: 'block', overflow: 'visible' }}
          >
            {activeSlices.length > 0 ? (
              paths
            ) : (
              <circle
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke="var(--border-primary, #e2e8f0)"
                strokeWidth="18"
              />
            )}
            {/* Center Cutout for Donut */}
            <circle
              cx={cx}
              cy={cy}
              r={radius * 0.58}
              fill="var(--bg-card, #ffffff)"
              style={{ filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.06))' }}
            />
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              fill="var(--text-primary, #0f172a)"
              fontSize="1.4rem"
              fontWeight="800"
            >
              {hoveredItem ? hoveredItem.value : totalScans}
            </text>
            <text
              x={cx}
              y={cy + 14}
              textAnchor="middle"
              fill="var(--text-secondary, #64748b)"
              fontSize="0.7rem"
              fontWeight="600"
              style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              {hoveredItem ? hoveredItem.displayName.slice(0, 10) : 'Total'}
            </text>
          </svg>
        </div>

        {/* Breakdown Progress Bars for ALL 8 Monitored Diseases */}
        <div className="admin-breakdown-list" style={{ maxHeight: '340px', overflowY: 'auto', paddingRight: '0.35rem' }}>
          {allItems.map((item) => {
            const isHovered = hoveredItem?.id === item.id;
            const hasData = item.value > 0;
            return (
              <div
                key={item.id}
                className="admin-breakdown-item"
                onMouseEnter={() => setHoveredItem(item)}
                onMouseLeave={() => setHoveredItem(null)}
                style={{
                  opacity: hoveredItem && !isHovered ? 0.45 : hasData ? 1 : 0.75,
                  transition: 'opacity 0.2s ease',
                  cursor: 'pointer',
                  padding: '0.2rem 0.4rem',
                  borderRadius: 'var(--radius-md)',
                  background: isHovered ? 'var(--bg-tertiary, rgba(0,0,0,0.03))' : 'transparent',
                }}
              >
                <div className="admin-breakdown-head">
                  <span className="admin-breakdown-tag">
                    <span
                      className="admin-color-dot"
                      style={{
                        backgroundColor: hasData ? item.color : '#94a3b8',
                        opacity: hasData ? 1 : 0.4,
                      }}
                    />
                    <span>{item.icon} {item.displayName}</span>
                  </span>
                  <span
                    className="admin-breakdown-pct"
                    style={{ fontWeight: hasData ? 700 : 500, color: hasData ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                  >
                    {item.value} ({item.percentage.toFixed(1)}%)
                  </span>
                </div>
                <div className="admin-progress-track" style={{ height: '6px' }}>
                  <div
                    className="admin-progress-fill"
                    style={{
                      width: `${item.percentage}%`,
                      backgroundColor: item.color,
                      opacity: hasData ? 1 : 0,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Generic Donut for Patients by Login Method ──────────────────────────────

function PatientDemographicsDonut({
  data,
  title,
  subtitle,
  size = 200,
}: {
  data: Record<string, number>;
  title: string;
  subtitle?: string;
  size?: number;
}): JSX.Element {
  const [hoveredSlice, setHoveredSlice] = useState<{ label: string; name: string; value: number } | null>(null);

  const total = useMemo(() => Object.values(data).reduce((sum, v) => sum + v, 0), [data]);

  const items = useMemo(() => {
    const googleCount = data['google'] || 0;
    const emailCount = (data['password'] || 0) + (data['email'] || 0) + (data['unknown'] || 0);
    const googlePct = total > 0 ? (googleCount / total) * 100 : 0;
    const emailPct = total > 0 ? (emailCount / total) * 100 : 0;

    return [
      { id: 'google', name: 'Google OAuth', value: googleCount, percentage: googlePct, color: '#4285F4', icon: '🔵' },
      { id: 'email', name: 'Email / Password', value: emailCount, percentage: emailPct, color: '#8B5CF6', icon: '📧' },
    ];
  }, [data, total]);

  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 12;
  let cumulativeAngle = -90;

  const paths = items.map((slice) => {
    const angle = (slice.value / (total || 1)) * 360;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + angle;
    cumulativeAngle = endAngle;

    const startRad = (Math.PI / 180) * startAngle;
    const endRad = (Math.PI / 180) * endAngle;

    const x1 = cx + radius * Math.cos(startRad);
    const y1 = cy + radius * Math.sin(startRad);
    const x2 = cx + radius * Math.cos(endRad);
    const y2 = cy + radius * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;
    const isHovered = hoveredSlice?.label === slice.id;

    if (items.filter((i) => i.value > 0).length === 1 && slice.value > 0) {
      return (
        <circle
          key={slice.id}
          cx={cx}
          cy={cy}
          r={radius}
          fill={slice.color}
          stroke="var(--bg-primary, #ffffff)"
          strokeWidth="3"
        />
      );
    }

    if (slice.value === 0) return null;

    const d = [
      `M ${cx} ${cy}`,
      `L ${x1} ${y1}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`,
      'Z',
    ].join(' ');

    return (
      <path
        key={slice.id}
        d={d}
        fill={slice.color}
        stroke="var(--bg-primary, #ffffff)"
        strokeWidth={isHovered ? '4' : '2'}
        onMouseEnter={() => setHoveredSlice({ label: slice.id, name: slice.name, value: slice.value })}
        onMouseLeave={() => setHoveredSlice(null)}
        style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
      />
    );
  });

  return (
    <div className="admin-chart-glass-panel">
      <div className="admin-panel-title-row">
        <div className="admin-panel-title">{title}</div>
        {subtitle && <span className="admin-panel-badge">{subtitle}</span>}
      </div>

      <div className="admin-donut-layout">
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block', overflow: 'visible' }}>
            {total > 0 ? (
              paths
            ) : (
              <circle cx={cx} cy={cy} r={radius} fill="none" stroke="var(--border-primary, #e2e8f0)" strokeWidth="18" />
            )}
            <circle
              cx={cx}
              cy={cy}
              r={radius * 0.58}
              fill="var(--bg-card, #ffffff)"
              style={{ filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.06))' }}
            />
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              fill="var(--text-primary, #0f172a)"
              fontSize="1.4rem"
              fontWeight="800"
            >
              {hoveredSlice ? hoveredSlice.value : total}
            </text>
            <text
              x={cx}
              y={cy + 14}
              textAnchor="middle"
              fill="var(--text-secondary, #64748b)"
              fontSize="0.7rem"
              fontWeight="600"
              style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}
            >
              {hoveredSlice ? hoveredSlice.name.slice(0, 10) : 'Patients'}
            </text>
          </svg>
        </div>

        <div className="admin-breakdown-list">
          {items.map((item) => (
            <div key={item.id} className="admin-breakdown-item">
              <div className="admin-breakdown-head">
                <span className="admin-breakdown-tag">
                  <span className="admin-color-dot" style={{ backgroundColor: item.color }} />
                  <span>{item.icon} {item.name}</span>
                </span>
                <span className="admin-breakdown-pct">
                  {item.value} ({item.percentage.toFixed(1)}%)
                </span>
              </div>
              <div className="admin-progress-track">
                <div
                  className="admin-progress-fill"
                  style={{ width: `${item.percentage}%`, backgroundColor: item.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Timestamp Formatter ─────────────────────────────────────────────────────

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ── Main Admin Cockpit Component ────────────────────────────────────────────

export default function AdminDashboardPage(): JSX.Element {
  const router = useRouter();
  const { user, loading } = useAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
  const [stats, setStats] = useState<AdminStatsData | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [scans, setScans] = useState<AdminScan[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [fetching, setFetching] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Search & Filter States
  const [scanSearch, setScanSearch] = useState<string>('');
  const [scanConditionFilter, setScanConditionFilter] = useState<string>('ALL');
  const [scanPage, setScanPage] = useState<number>(1);
  const scansPerPage = 10;

  const [userSearch, setUserSearch] = useState<string>('');
  const [userRoleFilter, setUserRoleFilter] = useState<string>('ALL');
  const [userPage, setUserPage] = useState<number>(1);
  const usersPerPage = 10;

  // Scan Inspection Modal State
  const [inspectedScan, setInspectedScan] = useState<AdminScan | null>(null);

  // Admin Promotion Modal State
  const [showPromoteModal, setShowPromoteModal] = useState<boolean>(false);
  const [promoteEmail, setPromoteEmail] = useState<string>('');
  const [promoteStatus, setPromoteStatus] = useState<{
    loading: boolean;
    success?: string;
    error?: string;
  }>({ loading: false });

  // Copy Feedback State
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Data Loader
  const loadData = useCallback(
    async (isManualRefresh = false) => {
      if (!user) return;
      if (isManualRefresh) setRefreshing(true);
      else setFetching(true);
      setPageError(null);

      try {
        const [verify, statsData, usersData, scansData] = await Promise.all([
          verifyAdmin(user),
          fetchAdminStats(user),
          fetchAdminUsers(user, 150),
          fetchAdminScans(user, 150),
        ]);

        if (!verify.isAdmin) {
          setPageError('Access restricted: You do not hold verified Administrator custom claims.');
          setFetching(false);
          setRefreshing(false);
          return;
        }

        setStats(statsData);
        setUsers(usersData.users);
        setScans(scansData.scans);
      } catch (err) {
        setPageError(
          err instanceof Error
            ? err.message
            : 'Unable to reach the VisionAI backend service. Ensure backend is running.'
        );
      } finally {
        setFetching(false);
        setRefreshing(false);
      }
    },
    [user]
  );

  const initialLoaded = useRef(false);
  useEffect(() => {
    if (!loading && !user) {
      router.replace('/admin/login');
    } else if (!loading && user && !initialLoaded.current) {
      initialLoaded.current = true;
      loadData();
    }
  }, [loading, user, router, loadData]);

  // Derived Metrics & Analytics
  const analytics = useMemo(() => {
    if (!scans.length) {
      return {
        avgConfidence: 0,
        highRiskCount: 0,
        highRiskRate: 0,
        googleUsers: 0,
        emailUsers: 0,
        detectedDiseasesCount: 0,
      };
    }
    const totalConf = scans.reduce((acc, s) => acc + (s.confidence ?? 0), 0);
    const avgConfidence = totalConf / scans.length;

    const highRiskScans = scans.filter((s) => {
      const matched = matchCondition(s.primaryLabel);
      return matched.id !== 'normal';
    });

    const detectedDiseases = new Set(scans.map((s) => matchCondition(s.primaryLabel).id));

    const googleCount = users.filter((u) => u.loginMethod === 'google').length;
    const emailCount = users.filter((u) => u.loginMethod !== 'google').length;

    return {
      avgConfidence,
      highRiskCount: highRiskScans.length,
      highRiskRate: (highRiskScans.length / scans.length) * 100,
      googleUsers: googleCount,
      emailUsers: emailCount,
      detectedDiseasesCount: detectedDiseases.size,
    };
  }, [scans, users]);

  // Filtered Scans
  const filteredScans = useMemo(() => {
    return scans.filter((s) => {
      const matched = matchCondition(s.primaryLabel);
      const matchesSearch =
        scanSearch === '' ||
        s.id.toLowerCase().includes(scanSearch.toLowerCase()) ||
        s.uid.toLowerCase().includes(scanSearch.toLowerCase()) ||
        (s.primaryLabel || '').toLowerCase().includes(scanSearch.toLowerCase()) ||
        matched.name.toLowerCase().includes(scanSearch.toLowerCase());

      const matchesCondition =
        scanConditionFilter === 'ALL' ||
        matched.id === scanConditionFilter ||
        matched.name.toLowerCase() === scanConditionFilter.toLowerCase() ||
        matched.shortName.toLowerCase() === scanConditionFilter.toLowerCase();

      return matchesSearch && matchesCondition;
    });
  }, [scans, scanSearch, scanConditionFilter]);

  const paginatedScans = useMemo(() => {
    const start = (scanPage - 1) * scansPerPage;
    return filteredScans.slice(start, start + scansPerPage);
  }, [filteredScans, scanPage]);

  const totalScanPages = Math.ceil(filteredScans.length / scansPerPage) || 1;

  // Filtered Users
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const matchesSearch =
        userSearch === '' ||
        u.email.toLowerCase().includes(userSearch.toLowerCase()) ||
        u.displayName.toLowerCase().includes(userSearch.toLowerCase()) ||
        u.uid.toLowerCase().includes(userSearch.toLowerCase());

      const matchesRole =
        userRoleFilter === 'ALL' ||
        u.role.toLowerCase() === userRoleFilter.toLowerCase();

      return matchesSearch && matchesRole;
    });
  }, [users, userSearch, userRoleFilter]);

  const paginatedUsers = useMemo(() => {
    const start = (userPage - 1) * usersPerPage;
    return filteredUsers.slice(start, start + usersPerPage);
  }, [filteredUsers, userPage]);

  const totalUserPages = Math.ceil(filteredUsers.length / usersPerPage) || 1;

  // Export Scans to CSV
  const exportScansCSV = () => {
    if (!scans.length) return;
    const headers = ['Scan ID', 'User UID', 'Primary Diagnosis', 'AI Confidence (%)', 'Model Backbone', 'Timestamp'];
    const rows = scans.map((s) => [
      s.id,
      s.uid,
      `"${s.primaryLabel}"`,
      (s.confidence ?? 0).toFixed(1),
      `"${s.modelId}"`,
      `"${s.timestamp ?? ''}"`,
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `VisionAI_Scans_Audit_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Handle Promote Admin
  const handlePromoteAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user || !promoteEmail.trim()) return;

    setPromoteStatus({ loading: true });
    try {
      const res = await promoteToAdmin(user, promoteEmail.trim());
      setPromoteStatus({
        loading: false,
        // Firebase custom claims are embedded in the JWT and only refresh when
        // the user's token is force-refreshed (i.e. they sign out and sign back in).
        success: `✅ ${res.email} has been promoted to Administrator. IMPORTANT: They must sign out and sign back in for admin access to activate.`,
      });
      setPromoteEmail('');
      loadData(true);
    } catch (err) {
      setPromoteStatus({
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to promote user to admin.',
      });
    }
  };

  if (loading || !user) {
    return (
      <main className="screening-main">
        <div className="container">
          <div className="welcome-section" aria-busy="true">
            <h1 className="welcome-title">Verifying Administrator Access…</h1>
            <p className="welcome-subtitle">Authenticating session security credentials</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <>
      <Navbar links={NAV_LINKS} />

      <main className="screening-main" style={{ paddingTop: '5.5rem', paddingBottom: '4rem' }}>
        <div className="admin-cockpit">
          {/* ── Top Header & Live Telemetry ── */}
          <header className="admin-header-glass">
            <div className="admin-header-info">
              <div className="admin-title-row">
                <h1 className="admin-title-text">Clinical Admin Cockpit</h1>
                <div className="admin-telemetry-badge">
                  <span className="admin-pulse-dot" />
                  <span>AI Inference Live</span>
                </div>
              </div>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary, #64748b)' }}>
                Multi-disease retinal pathology surveillance across all 8 clinical classes
              </p>
            </div>

            <div className="admin-header-actions">
              <button
                type="button"
                className="admin-action-btn"
                onClick={() => loadData(true)}
                disabled={refreshing || fetching}
                title="Refresh platform telemetry"
              >
                <span style={{ display: 'inline-block', transform: refreshing ? 'rotate(360deg)' : 'none', transition: 'transform 0.6s ease' }}>
                  🔄
                </span>
                <span>{refreshing ? 'Syncing…' : 'Refresh'}</span>
              </button>

              <button
                type="button"
                className="admin-action-btn"
                onClick={exportScansCSV}
                title="Export scan surveillance records to CSV"
              >
                <span>📥</span>
                <span>Export CSV</span>
              </button>

              <button
                type="button"
                className="admin-action-btn primary"
                onClick={() => {
                  setShowPromoteModal(true);
                  setPromoteStatus({ loading: false });
                }}
              >
                <span>🛡️</span>
                <span>Grant Admin</span>
              </button>
            </div>
          </header>

          {/* Error Alert */}
          {pageError && (
            <div className="error-state" style={{ display: 'block', marginBottom: '2rem' }} role="alert">
              <div className="error-icon" aria-hidden="true">⚠️</div>
              <h3 className="error-title">Security or Network Exception</h3>
              <p className="error-message">{pageError}</p>
            </div>
          )}

          {/* ── Navigation Tabs ── */}
          <nav className="admin-tab-nav" aria-label="Admin Dashboard Views">
            <button
              type="button"
              className={`admin-tab-item${activeTab === 'overview' ? ' active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              <span>📊</span>
              <span>Overview & Analytics</span>
            </button>
            <button
              type="button"
              className={`admin-tab-item${activeTab === 'scans' ? ' active' : ''}`}
              onClick={() => setActiveTab('scans')}
            >
              <span>🔬</span>
              <span>Clinical Scans Audit ({scans.length})</span>
            </button>
            <button
              type="button"
              className={`admin-tab-item${activeTab === 'users' ? ' active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <span>👥</span>
              <span>User Directory ({users.length})</span>
            </button>
            <button
              type="button"
              className={`admin-tab-item${activeTab === 'system' ? ' active' : ''}`}
              onClick={() => setActiveTab('system')}
            >
              <span>⚙️</span>
              <span>System & Access Control</span>
            </button>
          </nav>

          {/* Loading Indicator */}
          {fetching && !stats && (
            <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
              <div className="loading-bar" style={{ maxWidth: '320px', margin: '0 auto' }}>
                <div className="loading-progress" />
              </div>
              <p style={{ marginTop: '1.25rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                Aggregating clinical telemetry across all 8 disease classes…
              </p>
            </div>
          )}

          {stats && (
            <>
              {/* ══════════════════════════════════════════════════════════════
                  VIEW 1: EXECUTIVE OVERVIEW
                  ══════════════════════════════════════════════════════════════ */}
              {activeTab === 'overview' && (
                <>
                  {/* KPI Stat Cards Grid */}
                  <div className="admin-kpi-grid">
                    {/* Total Users */}
                    <div
                      className="admin-kpi-card"
                      style={{ '--accent-gradient': 'linear-gradient(90deg, #8B5CF6, #C084FC)' } as React.CSSProperties}
                    >
                      <div className="admin-kpi-top">
                        <span className="admin-kpi-label">Registered Patients</span>
                        <div
                          className="admin-kpi-icon-pill"
                          style={{ background: 'rgba(139, 92, 246, 0.12)', color: '#8B5CF6' }}
                        >
                          👥
                        </div>
                      </div>
                      <div className="admin-kpi-val">{stats.totalUsers}</div>
                      <div className="admin-kpi-footer">
                        <span>{analytics.googleUsers} Google • {analytics.emailUsers} Email</span>
                      </div>
                    </div>

                    {/* Total Scans */}
                    <div
                      className="admin-kpi-card"
                      style={{ '--accent-gradient': 'linear-gradient(90deg, #10B981, #34D399)' } as React.CSSProperties}
                    >
                      <div className="admin-kpi-top">
                        <span className="admin-kpi-label">Retinal Scans Processed</span>
                        <div
                          className="admin-kpi-icon-pill"
                          style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}
                        >
                          🔬
                        </div>
                      </div>
                      <div className="admin-kpi-val">{stats.totalScans}</div>
                      <div className="admin-kpi-footer">
                        <span className="admin-kpi-trend">
                          Avg {analytics.avgConfidence.toFixed(1)}% AI Confidence
                        </span>
                      </div>
                    </div>

                    {/* Actionable Pathologies */}
                    <div
                      className="admin-kpi-card"
                      style={{ '--accent-gradient': 'linear-gradient(90deg, #EF4444, #F87171)' } as React.CSSProperties}
                    >
                      <div className="admin-kpi-top">
                        <span className="admin-kpi-label">Actionable Pathologies</span>
                        <div
                          className="admin-kpi-icon-pill"
                          style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#EF4444' }}
                        >
                          ⚠️
                        </div>
                      </div>
                      <div className="admin-kpi-val">{analytics.highRiskCount}</div>
                      <div className="admin-kpi-footer">
                        <span>{analytics.highRiskRate.toFixed(1)}% of total scans</span>
                      </div>
                    </div>

                    {/* Monitored Diseases */}
                    <div
                      className="admin-kpi-card"
                      style={{ '--accent-gradient': 'linear-gradient(90deg, #0EA5E9, #38BDF8)' } as React.CSSProperties}
                    >
                      <div className="admin-kpi-top">
                        <span className="admin-kpi-label">Monitored Disease Spectrum</span>
                        <div
                          className="admin-kpi-icon-pill"
                          style={{ background: 'rgba(14, 165, 233, 0.12)', color: '#0EA5E9' }}
                        >
                          👁️
                        </div>
                      </div>
                      <div className="admin-kpi-val">8 Classes</div>
                      <div className="admin-kpi-footer">
                        <span style={{ color: '#10B981', fontWeight: 600 }}>
                          ● {analytics.detectedDiseasesCount} Detected • 8 Tracked
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Visual Charts Row */}
                  <div className="admin-charts-grid">
                    {/* Retinal Pathology Distribution (All 8 Conditions) */}
                    <ClinicalPathologyDonut
                      rawDistribution={stats.diseaseDistribution}
                      title="🔬 Retinal Pathology Distribution"
                      subtitle="Clinical Surveillance"
                    />

                    {/* Patient Authentication Demographics */}
                    <PatientDemographicsDonut
                      data={stats.loginMethodDistribution}
                      title="👥 Patient Authentication Demographics"
                      subtitle="Access Methods"
                    />
                  </div>

                  {/* Complete 8-Disease Clinical Surveillance Grid */}
                  <div className="admin-data-panel" style={{ marginBottom: '2rem' }}>
                    <div className="admin-panel-title-row">
                      <div className="admin-panel-title">
                        <span>👁️</span>
                        <span>Clinical Disease Surveillance Spectrum (All 8 Conditions)</span>
                      </div>
                      <span className="admin-panel-badge" style={{ background: 'rgba(14, 165, 233, 0.1)', color: '#0EA5E9' }}>
                        VisionAI Multi-Class Matrix
                      </span>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                        gap: '1rem',
                      }}
                    >
                      {MONITORED_DISEASES.map((cond) => {
                        let count = 0;
                        Object.entries(stats.diseaseDistribution).forEach(([lbl, c]) => {
                          if (matchCondition(lbl).id === cond.id) {
                            count += c;
                          }
                        });
                        const pct = stats.totalScans > 0 ? ((count / stats.totalScans) * 100).toFixed(1) : '0.0';
                        const hasCases = count > 0;

                        return (
                          <div
                            key={cond.id}
                            style={{
                              padding: '1rem 1.25rem',
                              borderRadius: 'var(--radius-xl)',
                              background: hasCases
                                ? 'var(--bg-secondary, #f8fafc)'
                                : 'var(--bg-tertiary, rgba(241, 245, 249, 0.5))',
                              border: `1px solid ${hasCases ? cond.color : 'var(--border-primary, #e2e8f0)'}`,
                              borderLeft: `5px solid ${cond.color}`,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '0.4rem',
                              transition: 'transform 0.2s ease',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 700, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span>{cond.icon}</span>
                                <span>{cond.name}</span>
                              </span>
                              <span
                                style={{
                                  padding: '0.15rem 0.55rem',
                                  borderRadius: '999px',
                                  fontSize: '0.75rem',
                                  fontWeight: 700,
                                  background: hasCases ? `${cond.color}22` : 'rgba(148, 163, 184, 0.15)',
                                  color: hasCases ? cond.color : '#94a3b8',
                                }}
                              >
                                {count} {count === 1 ? 'case' : 'cases'}
                              </span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                              <span>Platform Share:</span>
                              <strong>{pct}%</strong>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Recent Activity Mini-Grids */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
                    {/* Recent Scans Quick View */}
                    <div className="admin-data-panel">
                      <div className="admin-panel-title-row">
                        <div className="admin-panel-title">
                          <span>🔬</span>
                          <span>Recent Clinical Scans</span>
                        </div>
                        <button
                          type="button"
                          className="admin-filter-btn"
                          onClick={() => setActiveTab('scans')}
                        >
                          View All →
                        </button>
                      </div>
                      <div className="admin-table-container">
                        <table className="admin-table-styled">
                          <thead>
                            <tr>
                              <th>Condition</th>
                              <th>Confidence</th>
                              <th>Time</th>
                            </tr>
                          </thead>
                          <tbody>
                            {scans.slice(0, 5).map((s) => {
                              const confInfo = getConfidenceLevel(s.confidence ?? 0);
                              const matched = matchCondition(s.primaryLabel);
                              return (
                                <tr
                                  key={s.id}
                                  onClick={() => setInspectedScan(s)}
                                  style={{ cursor: 'pointer' }}
                                >
                                  <td>
                                    <span style={{ marginRight: '0.35rem' }}>{matched.icon}</span>
                                    <strong>{s.primaryLabel}</strong>
                                  </td>
                                  <td>
                                    <span
                                      className="admin-pill"
                                      style={{ background: confInfo.bgColor, color: confInfo.color }}
                                    >
                                      {confInfo.emoji} {(s.confidence ?? 0).toFixed(1)}%
                                    </span>
                                  </td>
                                  <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    {formatDateTime(s.timestamp)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Recent Users Quick View */}
                    <div className="admin-data-panel">
                      <div className="admin-panel-title-row">
                        <div className="admin-panel-title">
                          <span>👥</span>
                          <span>Recently Active Patients</span>
                        </div>
                        <button
                          type="button"
                          className="admin-filter-btn"
                          onClick={() => setActiveTab('users')}
                        >
                          View All →
                        </button>
                      </div>
                      <div className="admin-table-container">
                        <table className="admin-table-styled">
                          <thead>
                            <tr>
                              <th>User</th>
                              <th>Method</th>
                              <th>Role</th>
                            </tr>
                          </thead>
                          <tbody>
                            {users.slice(0, 5).map((u) => (
                              <tr key={u.uid}>
                                <td>
                                  <div style={{ fontWeight: 600 }}>{u.displayName || 'Anonymous Patient'}</div>
                                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{u.email}</div>
                                </td>
                                <td>
                                  <span className={`admin-pill admin-pill-${u.loginMethod}`}>
                                    {u.loginMethod === 'google' ? 'Google' : 'Email'}
                                  </span>
                                </td>
                                <td>
                                  <span className={`admin-pill admin-pill-${u.role}`}>
                                    {u.role === 'admin' ? '🛡️ Admin' : 'Patient'}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* ══════════════════════════════════════════════════════════════
                  VIEW 2: CLINICAL SCANS AUDIT REPOSITORY
                  ══════════════════════════════════════════════════════════════ */}
              {activeTab === 'scans' && (
                <div className="admin-data-panel">
                  <div className="admin-panel-title-row">
                    <div>
                      <div className="admin-panel-title">
                        <span>🔬</span>
                        <span>Clinical Retinal Scans Repository</span>
                      </div>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        Audited scan records with multi-class differential probabilities & cryptographic image hashes
                      </p>
                    </div>
                    <span className="admin-panel-badge">{filteredScans.length} Matched</span>
                  </div>

                  {/* Toolbar: Search + Filter Pills across ALL 8 conditions */}
                  <div className="admin-toolbar-row">
                    <div className="admin-search-wrapper">
                      <span className="admin-search-icon">🔍</span>
                      <input
                        type="text"
                        className="admin-search-input"
                        placeholder="Search by Scan ID, User UID, or condition…"
                        value={scanSearch}
                        onChange={(e) => {
                          setScanSearch(e.target.value);
                          setScanPage(1);
                        }}
                      />
                    </div>

                    <div className="admin-filter-group">
                      <button
                        type="button"
                        className={`admin-filter-btn${scanConditionFilter === 'ALL' ? ' active' : ''}`}
                        onClick={() => {
                          setScanConditionFilter('ALL');
                          setScanPage(1);
                        }}
                      >
                        All Conditions
                      </button>
                      {MONITORED_DISEASES.map((cond) => (
                        <button
                          key={cond.id}
                          type="button"
                          className={`admin-filter-btn${scanConditionFilter === cond.id ? ' active' : ''}`}
                          onClick={() => {
                            setScanConditionFilter(cond.id);
                            setScanPage(1);
                          }}
                        >
                          {cond.icon} {cond.shortName}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Scans Table */}
                  <div className="admin-table-container">
                    <table className="admin-table-styled">
                      <thead>
                        <tr>
                          <th>Scan ID / UID</th>
                          <th>Primary Diagnosis</th>
                          <th>AI Confidence</th>
                          <th>Model Architecture</th>
                          <th>Timestamp</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedScans.length === 0 ? (
                          <tr>
                            <td colSpan={6} style={{ textAlign: 'center', padding: '3rem', opacity: 0.6 }}>
                              No scans matched the selected search or filter criteria.
                            </td>
                          </tr>
                        ) : (
                          paginatedScans.map((s) => {
                            const confInfo = getConfidenceLevel(s.confidence ?? 0);
                            const matched = matchCondition(s.primaryLabel);
                            return (
                              <tr key={s.id}>
                                <td>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                                      {s.id.slice(0, 10)}…
                                    </span>
                                    <button
                                      type="button"
                                      onClick={() => copyToClipboard(s.id, s.id)}
                                      title="Copy Scan ID"
                                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.8rem', opacity: 0.6 }}
                                    >
                                      {copiedId === s.id ? '✅' : '📋'}
                                    </button>
                                  </div>
                                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                    User: {s.uid.slice(0, 8)}…
                                  </div>
                                </td>

                                <td>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                    <span>{matched.icon}</span>
                                    <strong>{s.primaryLabel}</strong>
                                  </div>
                                </td>

                                <td>
                                  <span
                                    className="admin-pill"
                                    style={{ background: confInfo.bgColor, color: confInfo.color }}
                                  >
                                    {confInfo.emoji} {(s.confidence ?? 0).toFixed(1)}% ({confInfo.level})
                                  </span>
                                </td>

                                <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                  {(s.modelId ?? '').split('/').pop() || 'RETFound-VisionAI'}
                                </td>

                                <td style={{ fontSize: '0.8rem' }}>{formatDateTime(s.timestamp)}</td>

                                <td>
                                  <button
                                    type="button"
                                    className="admin-filter-btn"
                                    onClick={() => setInspectedScan(s)}
                                    style={{ borderColor: '#0ea5e9', color: '#0ea5e9' }}
                                  >
                                    Inspect 🔍
                                  </button>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  <div className="admin-pagination-bar">
                    <div>
                      Showing {(scanPage - 1) * scansPerPage + 1}–
                      {Math.min(scanPage * scansPerPage, filteredScans.length)} of {filteredScans.length} records
                    </div>
                    <div className="admin-pagination-btns">
                      <button
                        type="button"
                        className="admin-page-nav-btn"
                        disabled={scanPage <= 1}
                        onClick={() => setScanPage((p) => p - 1)}
                      >
                        ← Prev
                      </button>
                      <span style={{ padding: '0 0.5rem', fontWeight: 600 }}>
                        Page {scanPage} of {totalScanPages}
                      </span>
                      <button
                        type="button"
                        className="admin-page-nav-btn"
                        disabled={scanPage >= totalScanPages}
                        onClick={() => setScanPage((p) => p + 1)}
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* ══════════════════════════════════════════════════════════════
                  VIEW 3: USER MANAGEMENT DIRECTORY
                  ══════════════════════════════════════════════════════════════ */}
              {activeTab === 'users' && (
                <div className="admin-data-panel">
                  <div className="admin-panel-title-row">
                    <div>
                      <div className="admin-panel-title">
                        <span>👥</span>
                        <span>Registered Patient & Clinician Directory</span>
                      </div>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        Firebase Auth verified user accounts and role assignments
                      </p>
                    </div>
                    <span className="admin-panel-badge">{filteredUsers.length} Users</span>
                  </div>

                  {/* Toolbar */}
                  <div className="admin-toolbar-row">
                    <div className="admin-search-wrapper">
                      <span className="admin-search-icon">🔍</span>
                      <input
                        type="text"
                        className="admin-search-input"
                        placeholder="Search by email, name, or UID…"
                        value={userSearch}
                        onChange={(e) => {
                          setUserSearch(e.target.value);
                          setUserPage(1);
                        }}
                      />
                    </div>

                    <div className="admin-filter-group">
                      {['ALL', 'Admin', 'User'].map((role) => (
                        <button
                          key={role}
                          type="button"
                          className={`admin-filter-btn${userRoleFilter === role ? ' active' : ''}`}
                          onClick={() => {
                            setUserRoleFilter(role);
                            setUserPage(1);
                          }}
                        >
                          {role === 'ALL' ? 'All Roles' : role === 'Admin' ? '🛡️ Admins' : '👤 Patients'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Table */}
                  <div className="admin-table-container">
                    <table className="admin-table-styled">
                      <thead>
                        <tr>
                          <th>User Profile</th>
                          <th>UID</th>
                          <th>Auth Provider</th>
                          <th>System Role</th>
                          <th>Last Active</th>
                          <th>Registered</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedUsers.length === 0 ? (
                          <tr>
                            <td colSpan={6} style={{ textAlign: 'center', padding: '3rem', opacity: 0.6 }}>
                              No users found matching query.
                            </td>
                          </tr>
                        ) : (
                          paginatedUsers.map((u) => (
                            <tr key={u.uid}>
                              <td>
                                <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                                  {u.displayName || 'Anonymous Patient'}
                                </div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{u.email}</div>
                              </td>

                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                  <span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                    {u.uid.slice(0, 10)}…
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => copyToClipboard(u.uid, u.uid)}
                                    title="Copy UID"
                                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', opacity: 0.6 }}
                                  >
                                    {copiedId === u.uid ? '✅' : '📋'}
                                  </button>
                                </div>
                              </td>

                              <td>
                                <span className={`admin-pill admin-pill-${u.loginMethod}`}>
                                  {u.loginMethod === 'google' ? '🔵 Google OAuth' : '📧 Email Auth'}
                                </span>
                              </td>

                              <td>
                                <span className={`admin-pill admin-pill-${u.role}`}>
                                  {u.role === 'admin' ? '🛡️ Administrator' : '👤 Patient'}
                                </span>
                              </td>

                              <td style={{ fontSize: '0.8rem' }}>{formatDateTime(u.lastLogin)}</td>
                              <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                {formatDateTime(u.createdAt)}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  <div className="admin-pagination-bar">
                    <div>
                      Showing {(userPage - 1) * usersPerPage + 1}–
                      {Math.min(userPage * usersPerPage, filteredUsers.length)} of {filteredUsers.length} users
                    </div>
                    <div className="admin-pagination-btns">
                      <button
                        type="button"
                        className="admin-page-nav-btn"
                        disabled={userPage <= 1}
                        onClick={() => setUserPage((p) => p - 1)}
                      >
                        ← Prev
                      </button>
                      <span style={{ padding: '0 0.5rem', fontWeight: 600 }}>
                        Page {userPage} of {totalUserPages}
                      </span>
                      <button
                        type="button"
                        className="admin-page-nav-btn"
                        disabled={userPage >= totalUserPages}
                        onClick={() => setUserPage((p) => p + 1)}
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* ══════════════════════════════════════════════════════════════
                  VIEW 4: SYSTEM & ACCESS CONTROL
                  ══════════════════════════════════════════════════════════════ */}
              {activeTab === 'system' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
                  {/* Admin Promotion Card */}
                  <div className="admin-data-panel">
                    <div className="admin-panel-title-row">
                      <div className="admin-panel-title">
                        <span>🛡️</span>
                        <span>Grant Administrator Privileges</span>
                      </div>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                      Promote existing clinical personnel or team members to Administrator status. This issues a cryptographically signed Firebase Custom Claim (<code>admin: true</code>).
                    </p>

                    <form onSubmit={handlePromoteAdmin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div>
                        <label
                          htmlFor="promote-email-field"
                          style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}
                        >
                          User Email Address
                        </label>
                        <input
                          id="promote-email-field"
                          type="email"
                          required
                          className="admin-search-input"
                          placeholder="doctor@hospital.org"
                          value={promoteEmail}
                          onChange={(e) => setPromoteEmail(e.target.value)}
                        />
                      </div>

                      {promoteStatus.success && (
                        <div
                          style={{
                            padding: '0.75rem 1rem',
                            borderRadius: 'var(--radius-lg)',
                            background: 'rgba(16, 185, 129, 0.1)',
                            border: '1px solid rgba(16, 185, 129, 0.25)',
                            color: '#10B981',
                            fontSize: '0.85rem',
                            fontWeight: 600,
                          }}
                        >
                          ✅ {promoteStatus.success}
                        </div>
                      )}

                      {promoteStatus.error && (
                        <div
                          style={{
                            padding: '0.75rem 1rem',
                            borderRadius: 'var(--radius-lg)',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.25)',
                            color: '#EF4444',
                            fontSize: '0.85rem',
                            fontWeight: 600,
                          }}
                        >
                          ⚠️ {promoteStatus.error}
                        </div>
                      )}

                      <button
                        type="submit"
                        className="admin-action-btn primary"
                        disabled={promoteStatus.loading || !promoteEmail.trim()}
                        style={{ justifySelf: 'start', alignSelf: 'flex-start' }}
                      >
                        {promoteStatus.loading ? 'Granting Claim…' : 'Promote to Admin 🛡️'}
                      </button>
                    </form>
                  </div>

                  {/* System Architecture & Telemetry Card */}
                  <div className="admin-data-panel">
                    <div className="admin-panel-title-row">
                      <div className="admin-panel-title">
                        <span>⚡</span>
                        <span>Clinical AI Telemetry</span>
                      </div>
                      <span className="admin-telemetry-badge">
                        <span className="admin-pulse-dot" />
                        <span>Online</span>
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.875rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-primary)' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>AI Model Backbone</span>
                        <strong style={{ fontFamily: 'monospace' }}>{stats.model}</strong>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-primary)' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Inference Device</span>
                        <strong style={{ color: '#10B981' }}>CPU (Optimized In-Memory Stream)</strong>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-primary)' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Database Persistence</span>
                        <strong>Google Cloud Firestore</strong>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-primary)' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Authentication RBAC</span>
                        <strong>Firebase Auth + Custom Claims</strong>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Clinical Coverage</span>
                        <strong style={{ color: '#10B981' }}>8 Full Differential Classes</strong>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          <p style={{ textAlign: 'center', marginTop: '3rem' }}>
            <Link href="/" className="nav-link">
              ← Return to Main Portal
            </Link>
          </p>
        </div>
      </main>

      {/* ── Scan Inspection Modal ── */}
      {inspectedScan && (
        <div
          className="admin-modal-backdrop"
          onClick={() => setInspectedScan(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-scan-title"
        >
          <div className="admin-modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <div className="admin-modal-title" id="modal-scan-title">
                <span>🔬</span>
                <span>Clinical Scan Differential Breakdown</span>
              </div>
              <button
                type="button"
                className="admin-modal-close-btn"
                onClick={() => setInspectedScan(null)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <div className="admin-modal-content">
              {/* Primary Diagnosis Callout */}
              <div
                style={{
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-xl)',
                  background: 'var(--bg-secondary, #f8fafc)',
                  border: '1px solid var(--border-primary, #e2e8f0)',
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                  Primary Finding
                </div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', margin: '0.25rem 0' }}>
                  {inspectedScan.primaryLabel}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                  {(() => {
                    const cInfo = getConfidenceLevel(inspectedScan.confidence ?? 0);
                    return (
                      <span
                        className="admin-pill"
                        style={{ background: cInfo.bgColor, color: cInfo.color }}
                      >
                        {cInfo.emoji} {(inspectedScan.confidence ?? 0).toFixed(1)}% ({cInfo.level} Confidence)
                      </span>
                    );
                  })()}
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    • {formatDateTime(inspectedScan.timestamp)}
                  </span>
                </div>
              </div>

              {/* Multi-Class Differential Probability Scores */}
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.875rem', fontWeight: 700, marginBottom: '0.85rem' }}>
                  Differential Probability Distribution:
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {(inspectedScan.allResults && inspectedScan.allResults.length > 0
                    ? inspectedScan.allResults
                    : [{ label: inspectedScan.primaryLabel, confidence: inspectedScan.confidence }]
                  ).map((pred) => {
                    const meta = matchCondition(pred.label);
                    return (
                      <div key={pred.label}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                          <span style={{ fontWeight: 600 }}>
                            {meta.icon} {pred.label}
                          </span>
                          <span style={{ fontWeight: 700 }}>{(pred.confidence ?? 0).toFixed(1)}%</span>
                        </div>
                        <div className="admin-progress-track">
                          <div
                            className="admin-progress-fill"
                            style={{
                              width: `${Math.min(Math.max(pred.confidence, 0), 100)}%`,
                              backgroundColor: meta.color,
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Metadata Attributes */}
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <div><strong>Scan ID:</strong> {inspectedScan.id}</div>
                <div><strong>Patient UID:</strong> {inspectedScan.uid}</div>
                <div><strong>Model ID:</strong> {inspectedScan.modelId}</div>
                {inspectedScan.imageHash && <div><strong>SHA-256 Hash:</strong> <code>{inspectedScan.imageHash}</code></div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Promote Admin Modal ── */}
      {showPromoteModal && (
        <div
          className="admin-modal-backdrop"
          onClick={() => setShowPromoteModal(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="admin-modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="admin-modal-header">
              <div className="admin-modal-title">
                <span>🛡️</span>
                <span>Grant Administrator Role</span>
              </div>
              <button
                type="button"
                className="admin-modal-close-btn"
                onClick={() => setShowPromoteModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="admin-modal-content">
              <form onSubmit={handlePromoteAdmin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                  Enter the email address of the registered user you wish to grant platform administrative rights to.
                </p>

                <div>
                  <label
                    htmlFor="dialog-promote-email"
                    style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}
                  >
                    User Email
                  </label>
                  <input
                    id="dialog-promote-email"
                    type="email"
                    required
                    className="admin-search-input"
                    placeholder="user@example.com"
                    value={promoteEmail}
                    onChange={(e) => setPromoteEmail(e.target.value)}
                  />
                </div>

                {promoteStatus.success && (
                  <div
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: 'var(--radius-lg)',
                      background: 'rgba(16, 185, 129, 0.1)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      color: '#10B981',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                    }}
                  >
                    ✅ {promoteStatus.success}
                  </div>
                )}

                {promoteStatus.error && (
                  <div
                    style={{
                      padding: '0.75rem 1rem',
                      borderRadius: 'var(--radius-lg)',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      color: '#EF4444',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                    }}
                  >
                    ⚠️ {promoteStatus.error}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                  <button
                    type="button"
                    className="admin-action-btn"
                    onClick={() => setShowPromoteModal(false)}
                  >
                    Close
                  </button>
                  <button
                    type="submit"
                    className="admin-action-btn primary"
                    disabled={promoteStatus.loading || !promoteEmail.trim()}
                  >
                    {promoteStatus.loading ? 'Promoting…' : 'Confirm Grant 🛡️'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      <MinimalFooter />
    </>
  );
}
