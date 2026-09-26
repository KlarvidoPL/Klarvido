import klarvidoLogo from '../../../../images/klarvido-logo.png';

export const AuthLogo = () => {
  return (
    <div className="my-3 flex h-[72px] w-[190px] items-center justify-center">
      <img src={klarvidoLogo} alt="Klarvido" className="h-auto w-full object-contain" />
    </div>
  );
};
