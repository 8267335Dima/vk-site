// frontend/src/components/ErrorBoundary.js
import React from 'react';
import { Paper, Typography, Button, Box } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Обновляем состояние, чтобы следующий рендер показал запасной UI.
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Здесь можно отправить информацию об ошибке в сервис мониторинга (Sentry, LogRocket и т.д.)
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Вы можете отрендерить любой запасной UI
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
            <Paper sx={{ p: 4, textAlign: 'center', maxWidth: 500 }}>
                <ErrorOutlineIcon color="error" sx={{ fontSize: 60, mb: 2 }}/>
                <Typography variant="h5" component="h1" gutterBottom>
                    Что-то пошло не так.
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    В приложении произошла ошибка. Пожалуйста, попробуйте перезагрузить страницу.
                </Typography>
                <Button 
                    variant="contained" 
                    onClick={() => window.location.reload()}
                >
                    Перезагрузить
                </Button>
            </Paper>
        </Box>
      );
    }

    return this.props.children; 
  }
}

export default ErrorBoundary;