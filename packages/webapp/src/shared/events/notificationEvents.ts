import { NotificationTypes } from '@sb/webapp-notifications';

type GetEventsProps = {
  reloadCommonQuery: () => void;
};

const getNotificationEvents = ({ reloadCommonQuery }: GetEventsProps) => ({
  [NotificationTypes.TENANT_INVITATION_CREATED]: reloadCommonQuery,
  // Drop the deleted organization from the switcher right away for members who are online
  [NotificationTypes.TENANT_DELETED]: reloadCommonQuery,
});
export default getNotificationEvents;
