// frontend/src/theme.js
import { createTheme, responsiveFontSizes } from '@mui/material/styles';

const palette = {
  primary: '#5E5CE6', // Насыщенный индиго
  secondary: '#00BAE2', // Яркий циан
  backgroundDefault: '#0D0E12', // Очень темный, почти черный
  backgroundPaper: '#17181D', // Темно-серый для карточек
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A3BD', // Приглушенный серо-голубой
  success: '#34C759',
  warning: '#FF9500',
  error: '#FF3B30',
  info: '#007AFF',
  divider: 'rgba(160, 163, 189, 0.15)', // Полупрозрачный цвет текста
};

let theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: palette.primary },
    secondary: { main: palette.secondary },
    background: {
      default: palette.backgroundDefault,
      paper: palette.backgroundPaper,
    },
    text: {
      primary: palette.textPrimary,
      secondary: palette.textSecondary,
    },
    success: { main: palette.success },
    warning: { main: palette.warning },
    error: { main: palette.error },
    info: { main: palette.info },
    divider: palette.divider,
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h1: { fontWeight: 800, letterSpacing: '-0.03em' },
    h2: { fontWeight: 700, letterSpacing: '-0.025em' },
    h3: { fontWeight: 700, letterSpacing: '-0.02em' },
    h4: { fontWeight: 600, letterSpacing: '-0.01em' },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: {
        textTransform: 'none',
        fontWeight: 600,
        fontSize: '1rem',
    }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: `1px solid ${palette.divider}`,
          borderRadius: '16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          padding: '10px 24px',
          transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: `0 8px 20px ${palette.primary}40`,
          },
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
             boxShadow: `0 8px 20px ${palette.primary}40`,
          }
        },
        containedPrimary: {
           background: `linear-gradient(45deg, ${palette.primary} 30%, ${palette.secondary} 90%)`,
        }
      },
    },
    MuiTooltip: {
        styleOverrides: {
            tooltip: {
                backgroundColor: 'rgba(30, 31, 37, 0.9)',
                backdropFilter: 'blur(8px)',
                borderRadius: '8px',
                border: `1px solid ${palette.divider}`,
                fontSize: '0.875rem',
            },
            arrow: {
                color: 'rgba(30, 31, 37, 0.9)',
            }
        }
    },
    MuiChip: {
        styleOverrides: {
            root: {
                borderRadius: '8px',
                fontWeight: 600,
            }
        }
    }
  },
});

theme = responsiveFontSizes(theme);

export { theme };

export const globalStyles = `
  body {
    background-color: ${palette.backgroundDefault};
  }
  
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background-color: ${palette.divider};
    border-radius: 4px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background-color: rgba(160, 163, 189, 0.3);
  }
`;