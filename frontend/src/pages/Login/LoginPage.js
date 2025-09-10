// frontend/src/pages/Login/LoginPage.js
import React, { useState } from 'react';
import { Paper, Typography, TextField, Button, CircularProgress, Alert, Box, Tooltip } from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { motion } from 'framer-motion';
import { loginWithVkToken } from 'api.js';
import { useUserStore } from 'store/userStore';
import { loginPageContent as content } from 'content/loginPageContent';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    return content.errors.default;
};

export default function LoginPage() {
    const login = useUserStore((state) => state.login);
    const [vkTokenInput, setVkTokenInput] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleTokenLogin = async () => {
        if (!vkTokenInput.trim()) {
            setMessage(content.errors.emptyToken);
            return;
        }

        let tokenToUse = vkTokenInput.trim();
        if (tokenToUse.includes('access_token=')) {
            try {
                const params = new URLSearchParams(tokenToUse.split('#')[1]);
                tokenToUse = params.get('access_token');
                if (!tokenToUse) throw new Error();
            } catch {
                setMessage(content.errors.invalidUrl);
                return;
            }
        }

        setLoading(true);
        setMessage('');
        try {
          const response = await loginWithVkToken(tokenToUse);
          login(response.data.access_token);
        } catch (error) {
          const errorMessage = getErrorMessage(error);
          setMessage(errorMessage);
        }
        setLoading(false);
    };

    return (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Paper sx={{ p: {xs: 3, md: 5}, mt: { xs: 4, md: 8 }, textAlign: 'center', maxWidth: 500, mx: 'auto' }}>
                <Typography component="h1" variant="h4" gutterBottom sx={{ fontWeight: 600 }}>
                    {content.title}
                </Typography>
                <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 4}}>
                    <Typography variant="body1" color="text.secondary">
                        {content.subtitle}
                    </Typography>
                    <Tooltip
                      title={
                          <Box sx={{ textAlign: 'left' }}>
                              <Typography variant="caption" display="block" sx={{ mb: 1 }} dangerouslySetInnerHTML={{ __html: content.tooltip.step1 }} />
                              <Typography variant="caption" display="block" sx={{ mb: 1 }}>{content.tooltip.step2}</Typography>
                              <Typography variant="caption" display="block">{content.tooltip.step3}</Typography>
                          </Box>
                      }
                      placement="right"
                      arrow
                    >
                        <HelpOutlineIcon fontSize="small" color="secondary" sx={{ cursor: 'help' }}/>
                    </Tooltip>
                </Box>
                <TextField
                    fullWidth
                    label={content.textFieldLabel}
                    variant="outlined"
                    value={vkTokenInput}
                    onChange={(e) => setVkTokenInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && !loading && handleTokenLogin()}
                    sx={{ mb: 2 }}
                />
                <Button
                    variant="contained"
                    size="large"
                    onClick={handleTokenLogin}
                    disabled={loading}
                    sx={{ width: '100%', py: 1.5, fontSize: '1.1rem' }}
                >
                    {loading ? <CircularProgress size={26} color="inherit" /> : content.buttonText}
                </Button>
                {message && <Alert severity={'error'} sx={{ mt: 3, textAlign: 'left' }}>{message}</Alert>}
            </Paper>
        </motion.div>
    );
}