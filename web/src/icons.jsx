const base = { viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', strokeWidth:1.75, strokeLinecap:'round', strokeLinejoin:'round' }

function mk(children){
  return function Icon({ size = 20, ...rest }){
    return <svg {...base} width={size} height={size} {...rest}>{children}</svg>
  }
}

export const ISearch = mk(<><circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4.5 4.5"/></>)
export const ICrosshair = mk(<><circle cx="12" cy="12" r="9"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/></>)
export const IHistory = mk(<><path d="M3 12a9 9 0 1 0 2.6-6.4L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 3"/></>)
export const IKey = mk(<><circle cx="8" cy="14" r="4"/><path d="m11 11 10-10"/><path d="m18 3 3 3"/><path d="m15 6 3 3"/></>)
export const ICommand = mk(<path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3"/>)
export const IX = mk(<><path d="M18 6 6 18"/><path d="m6 6 12 12"/></>)
export const IChevD = mk(<path d="m6 9 6 6 6-6"/>)
export const IChevR = mk(<path d="m9 6 6 6-6 6"/>)
export const IExt = mk(<><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>)
export const ICopy = mk(<><rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></>)
export const ICheck = mk(<path d="m20 6-11 11-5-5"/>)
export const IOkCircle = mk(<><circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 5-5"/></>)
export const IWarn = mk(<><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></>)
export const ICrit = mk(<><path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86L7.86 2Z"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></>)
export const IInfo = mk(<><circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/></>)
export const IPlay = mk(<path d="M6 4.5v15l13-7.5L6 4.5Z"/>)
export const IStop = mk(<rect x="6" y="6" width="12" height="12" rx="2"/>)
export const IDownload = mk(<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></>)
export const IRefresh = mk(<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></>)
export const ITrash = mk(<><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></>)
export const IFileSearch = mk(<><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/><circle cx="11.5" cy="12.5" r="2.5"/><path d="m13.3 14.3 1.7 1.7"/></>)
export const IGlobe = mk(<><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a13.9 13.9 0 0 1 3.6 9 13.9 13.9 0 0 1-3.6 9 13.9 13.9 0 0 1-3.6-9A13.9 13.9 0 0 1 12 3Z"/></>)
export const IMail = mk(<><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></>)
export const IPhone = mk(<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92Z"/>)
export const IAt = mk(<><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/></>)
export const INetwork = mk(<><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></>)
export const IShapes = mk(<><path d="M12 2 20 9H4l8-7Z"/><rect x="14" y="14" width="8" height="8" rx="1"/><circle cx="7" cy="17.5" r="3.5"/></>)
export const IShield = mk(<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1Z"/>)
export const IPanel = mk(<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></>)
export const IActivity = mk(<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>)
export const IClock = mk(<><circle cx="12" cy="12" r="9"/><path d="m12 6 0 6 4 2"/></>)
export const IFile = mk(<><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M15 2v5h5"/></>)

export function RadarArt(){
  return (
    <svg width="170" height="150" viewBox="0 0 170 150" fill="none">
      { [26,48,70].map((r)=>(
        <circle key={r} cx="85" cy="75" r={r} stroke="#C4BCA6" strokeWidth="1.25"/>
      ))}
      <path d="M85 7v136M17 75h136" stroke="#D9D2BF" strokeWidth="1" opacity=".8"/>
      <path d="M85 75 L138 30 A68 68 0 0 1 151 72 Z" fill="rgba(30,107,79,.10)"/>
      <line x1="85" y1="75" x2="146" y2="26" stroke="#1E6B4F" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="85" cy="75" r="4" fill="#1E6B4F"/>
      <circle cx="118" cy="52" r="3" fill="#B4690E"/>
      <circle cx="60" cy="100" r="3" fill="#1E6B4F"/>
      <circle cx="104" cy="98" r="2.5" fill="#C4BCA6"/>
      <circle cx="44" cy="56" r="2.5" fill="#C4BCA6"/>
    </svg>
  )
}
