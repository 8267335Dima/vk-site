// frontend/src/theme.js
import { createTheme, responsiveFontSizes } from '@mui/material/styles';

const palette = {
  primary: '#7E57C2', // Насыщенный фиолетовый
  secondary: '#00B0FF', // Яркий голубой
  backgroundDefault: '#121212', // Темный фон
  backgroundPaper: '#1E1E1E', // Фон карточек
  textPrimary: '#E0E0E0', // Светлый текст
  textSecondary: '#BDBDBD', // Менее яркий текст
  gradientStart: 'rgba(30, 30, 30, 0)',
  gradientEnd: 'rgba(30, 30, 30, 0.7)',
  success: '#00E676',
  warning: '#FFC400',
  error: '#FF1744',
  info: '#29B6F6',
};

let theme = createTheme({
  palette: {
    mode: 'dark', // Темная тема
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
    divider: 'rgba(255, 255, 255, 0.12)',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    allVariants: {
      color: palette.textPrimary,
    },
    h1: { fontWeight: 800 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 700 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none', // Убираем градиент по умолчанию
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 20,
          boxShadow: '0 4px 30px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '1rem',
          transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: `0 6px 20px rgba(126, 87, 194, 0.4)`,
          },
        },
        containedPrimary: {
           backgroundImage: `linear-gradient(45deg, ${palette.primary} 30%, ${palette.secondary} 90%)`,
        }
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(18, 18, 18, 0.7)',
          backdropFilter: 'blur(10px)',
          boxShadow: 'none',
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
        },
      },
    },
    MuiTooltip: {
        styleOverrides: {
            tooltip: {
                backgroundColor: 'rgba(40, 40, 50, 0.9)',
                backdropFilter: 'blur(5px)',
                borderRadius: 8,
                border: '1px solid rgba(255, 255, 255, 0.1)',
            },
            arrow: {
                color: 'rgba(40, 40, 50, 0.9)',
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
    background-image: radial-gradient(circle at 1% 1%, ${palette.primary}33, ${palette.backgroundDefault} 25%),
                      radial-gradient(circle at 99% 99%, ${palette.secondary}33, ${palette.backgroundDefault} 25%);
    background-attachment: fixed;
    min-height: 100vh;
  }
  
  /* Modern Scrollbar */
  ::-webkit-scrollbar {
    width: 8px;
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }
  ::-webkit-scrollbar-thumb {
    background-color: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background-color: rgba(255, 255, 255, 0.4);
  }
`;