// frontend/src/pages/Dashboard/components/ActionModal.js
import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import { ActionModalContent } from './ActionModalContent';
import { useActionModalState } from 'hooks/useActionModalState';

const ActionModal = ({ open, onClose, onSubmit, title, actionKey }) => {
    const { params, getModalTitle, handleParamChange } = useActionModalState(open, actionKey, title);

    const handleSubmit = () => {
        onSubmit(actionKey, params);
        onClose();
    };
    
    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle sx={{ fontWeight: 600 }}>{getModalTitle()}</DialogTitle>
            <DialogContent dividers>
                <ActionModalContent 
                    actionKey={actionKey}
                    params={params}
                    onParamChange={handleParamChange}
                />
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
                <Button onClick={onClose}>Отмена</Button>
                <Button onClick={handleSubmit} variant="contained">Запустить</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ActionModal;