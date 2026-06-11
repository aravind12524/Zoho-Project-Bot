import React from 'react';
import './ConfirmationModal.css';

function ConfirmationModal({ details, onConfirm, onCancel }) {
  const isDelete = details?.action === 'delete_task';

  const getDescription = () => {
    if (!details) return '';
    switch (details.action) {
      case 'create_task':
        return `Create task "${details.name}" in project "${details.project_name || details.project_id}"`;
      case 'update_task':
        return `Update task #${details.task_id} in "${details.project_name || details.project_id}"\nChanges: ${details.changes}`;
      case 'delete_task':
        return `Delete task #${details.task_id} from "${details.project_name || details.project_id}"\nThis action cannot be undone.`;
      default:
        return JSON.stringify(details, null, 2);
    }
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className={`modal-icon ${isDelete ? 'danger' : 'warning'}`}>
            {isDelete ? (
              <svg viewBox="0 0 24 24">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6" /><path d="M14 11v6" />
                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            )}
          </div>
          <div>
            <div className="modal-title">Confirm action</div>
            <div className="modal-subtitle">Review the details below before proceeding</div>
          </div>
        </div>

        <div className={`modal-detail-box${isDelete ? ' danger' : ''}`}>
          {getDescription().split('\n').map((line, i, arr) => (
            <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
          ))}
        </div>

        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={`btn-confirm${isDelete ? ' danger' : ''}`}
            onClick={onConfirm}
          >
            {isDelete ? 'Yes, delete' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmationModal;
