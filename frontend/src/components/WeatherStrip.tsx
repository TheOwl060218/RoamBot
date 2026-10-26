import { Cloud, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Sun, Thermometer } from 'lucide-react'
import type { DailyWeather } from '../api/types'
import '../styles/weather-strip.css'

function weatherIcon(condition: string) {
  if (/雷|thunder/i.test(condition)) return CloudLightning
  if (/雪|snow|sleet/i.test(condition)) return CloudSnow
  if (/雨|rain|drizzle|shower/i.test(condition)) return CloudRain
  if (/雾|霾|fog|haze|mist/i.test(condition)) return CloudFog
  if (/多云|partly/i.test(condition)) return CloudSun
  if (/阴|cloud|overcast/i.test(condition)) return Cloud
  if (/晴|sun|clear/i.test(condition)) return Sun
  return Thermometer
}

export function WeatherStrip({ days }: { days: DailyWeather[] | null | undefined }) {
  if (!days?.length) return null
  return <section className='weather-strip' aria-label='天气预报'>
    <div className='weather-strip-heading'>天气</div>
    <div className='weather-strip-scroll' role='region' aria-label='逐日天气，可左右滚动' tabIndex={0}>
      <ul className='weather-strip-days'>
        {days.map(day => {
          const Icon = weatherIcon(day.condition)
          return <li className='weather-strip-day' key={day.date}>
            <time dateTime={day.date} title={day.date}>{day.date.slice(5).replace('-', '/')}</time>
            <Icon className='weather-strip-icon' size={25} strokeWidth={1.5} aria-hidden='true' />
            <span className='weather-strip-condition'>{day.condition}</span>
            <span className='weather-strip-temperature'>{day.temp_min_c}–{day.temp_max_c}°C</span>
          </li>
        })}
      </ul>
    </div>
  </section>
}
