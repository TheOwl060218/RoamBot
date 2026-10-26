import xiaohongshuLogo from '../assets/brands/xiaohongshu.svg'

export function PlaceGuideLink({ name, city }: { name: string; city: string }) {
  const keyword = [city.trim(), name.trim()].filter(Boolean).join(' ')
  const url = `https://www.xiaohongshu.com/search_result?${new URLSearchParams({ keyword, source: 'web_search_result_notes' })}`
  return <a className='text-button place-guide-link' href={url} target='_blank' rel='noopener noreferrer'
    title={`在小红书搜索“${keyword}”（新窗口）`}>
    <img className='place-guide-logo' src={xiaohongshuLogo} width={24} height={24} alt='' aria-hidden='true' />小红书攻略
  </a>
}
