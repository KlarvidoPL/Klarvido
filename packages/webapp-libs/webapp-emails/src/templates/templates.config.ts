import { EmailTemplateDefinition, EmailTemplateType } from '../types';
import * as AccountActivation from './accountActivation';
import * as BackupReady from './backupReady';
import * as InvoiceCreated from './invoiceCreated';
import * as InvoiceFileAdded from './invoiceFileAdded';
import * as InvoiceRequestAssigned from './invoiceRequestAssigned';
import * as InvoiceRequestComment from './invoiceRequestComment';
import * as InvoiceRequestMention from './invoiceRequestMention';
import * as OtpDisabled from './otpDisabled';
import * as OtpEnabled from './otpEnabled';
import * as OtpReplaced from './otpReplaced';
import * as PasswordChanged from './passwordChanged';
import * as PasswordReset from './passwordReset';
import * as PasswordSet from './passwordSet';
import * as ProjectNoteMention from './projectNoteMention';
import * as SignupGuidance from './signupGuidance';
import * as SocialAccountLinked from './socialAccountLinked';
import * as SubscriptionError from './subscriptionError';
import * as TenantDeleted from './tenantDeleted';
import * as TenantInvitation from './tenantInvitation';
import * as TrialExpiresSoon from './trialExpiresSoon';
import * as UserExport from './userExport';
import * as UserExportAdmin from './userExportAdmin';

//<-- INJECT EMAIL TEMPLATE IMPORT -->

export const templates: Record<EmailTemplateType, EmailTemplateDefinition> = {
  [EmailTemplateType.ACCOUNT_ACTIVATION]: AccountActivation,
  [EmailTemplateType.PASSWORD_RESET]: PasswordReset,
  [EmailTemplateType.SUBSCRIPTION_ERROR]: SubscriptionError,
  [EmailTemplateType.TRIAL_EXPIRES_SOON]: TrialExpiresSoon,
  [EmailTemplateType.USER_EXPORT]: UserExport,
  [EmailTemplateType.USER_EXPORT_ADMIN]: UserExportAdmin,
  [EmailTemplateType.TENANT_INVITATION]: TenantInvitation,
  [EmailTemplateType.INVOICE_REQUEST_ASSIGNED]: InvoiceRequestAssigned,
  [EmailTemplateType.INVOICE_REQUEST_COMMENT]: InvoiceRequestComment,
  [EmailTemplateType.INVOICE_REQUEST_MENTION]: InvoiceRequestMention,
  [EmailTemplateType.INVOICE_CREATED]: InvoiceCreated,
  [EmailTemplateType.INVOICE_FILE_ADDED]: InvoiceFileAdded,
  [EmailTemplateType.PROJECT_NOTE_MENTION]: ProjectNoteMention,
  [EmailTemplateType.BACKUP_READY]: BackupReady,
  [EmailTemplateType.TENANT_DELETED]: TenantDeleted,
  [EmailTemplateType.SOCIAL_ACCOUNT_LINKED]: SocialAccountLinked,
  [EmailTemplateType.OTP_ENABLED]: OtpEnabled,
  [EmailTemplateType.OTP_DISABLED]: OtpDisabled,
  [EmailTemplateType.SIGNUP_GUIDANCE]: SignupGuidance,
  [EmailTemplateType.PASSWORD_CHANGED]: PasswordChanged,
  [EmailTemplateType.OTP_REPLACED]: OtpReplaced,
  [EmailTemplateType.PASSWORD_SET]: PasswordSet,
  //<-- INJECT EMAIL TEMPLATE -->
};
