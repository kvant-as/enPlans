document.addEventListener('DOMContentLoaded', function() {
    const confirmInput = document.getElementById('confirm-email-field');
    const deleteProfileBtn = document.getElementById('deleteProfileBtn');
    const currentUserEmailElement = document.getElementById('current_user_email');
    const currentUserEmail = currentUserEmailElement ? currentUserEmailElement.value : '';
    
    if (confirmInput && deleteProfileBtn) {
        deleteProfileBtn.disabled = true;
        
        confirmInput.addEventListener('input', function() {
            const enteredEmail = this.value.trim();
            
            if (enteredEmail === currentUserEmail) {
                deleteProfileBtn.disabled = false;
                this.classList.remove('input-invalid');
                this.classList.add('input-valid');
            } else {
                deleteProfileBtn.disabled = true;
                this.classList.remove('input-valid');
                if (enteredEmail.length > 0) {
                    this.classList.add('input-invalid');
                } else {
                    this.classList.remove('input-invalid');
                }
            }
        });
    }
    
    if (document.getElementById('deleteProfileBtn')) {
        initConfirmModal({
            triggerId: 'deleteProfileBtn',
            formId: 'deleteProfile_form',
            modalId: 'confirmModal2',
            yesId: 'confirmYes',
            noId: 'confirmNo',
            textId: 'modal-text',
            modalText: 'Вы действительно хотите удалить свой профиль в enPlans?',
            textSecondId: 'modal-text-second',
            modalTextSecond: 'Это действие нельзя будет отменить.'
        });
    }
});