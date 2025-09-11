// frontend/src/pages/Dashboard/components/ActionModal.js
import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import ActionModalContent from './ActionModalContent';
import { useActionModalState } from 'hooks/useActionModalState';
import { content } from 'content/content';

const ActionModal = ({ open, onClose, onSubmit, title, actionKey }) => {
    const { params, getModalTitle, handleParamChange, getActionLimit } = useActionModalState(open, actionKey, title);

    const handleSubmit = () => {
        onSubmit(actionKey, params);
        onClose();
    };
    
    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" PaperProps={{ sx: { borderRadius: 4 } }}>
            <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>{getModalTitle()}</DialogTitle>
            <DialogContent dividers>
                <ActionModalContent 
                    actionKey={actionKey}
                    params={params}
                    onParamChange={handleParamChange}
                    limit={getActionLimit()}
                />
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
                <Button onClick={onClose}>{content.modal.cancelButton}</Button>
                <Button onClick={handleSubmit} variant="contained">{content.modal.launchButton}</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ActionModal;