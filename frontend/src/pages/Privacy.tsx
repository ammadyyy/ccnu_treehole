export default function Privacy() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 text-sm leading-7 text-gray-700">
      <h1 className="text-xl font-bold text-gray-900">隐私说明</h1>

      <section>
        <h2 className="text-base font-semibold text-gray-900">匿名机制</h2>
        <p>
          回声洞采用「账号 + 面具」双层身份。你注册时使用的邮箱仅用于登录，不会对其他用户公开。
          发帖、回应都以随机面具「匿名者·xxxx」身份展示，其他用户无法通过公开页面判断两个面具是否属于同一个账号。
        </p>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-900">我们收集的数据</h2>
        <ul className="mt-2 list-disc pl-5 space-y-1">
          <li>注册邮箱（仅本人与管理员可见）</li>
          <li>密码哈希（不保存明文）</li>
          <li>面具、帖子、回应、图片及其说明</li>
          <li>登录、发帖、回应、举报时的 IP 地址与 User-Agent</li>
        </ul>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-900">数据保留</h2>
        <ul className="mt-2 list-disc pl-5 space-y-1">
          <li>帖子、回应与图片在删除前持续保留；作者删除后正文与图片被彻底删除</li>
          <li>登录、发帖、回应的 IP 与 User-Agent 永久保留，供管理员在举报处置场景查看</li>
          <li>通知永久保留，直到账号注销或相关内容被删除</li>
        </ul>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-900">管理员可查看的信息</h2>
        <p>
          管理员在处理举报、管理内容时可查看面具对应的站内账号邮箱、注册时间、最后登录时间与
          IP。查看已注销面具的账号映射会记录审计日志；查看普通面具的映射不记录日志。
        </p>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-900">注销账号</h2>
        <p>
          你可以在「账号设置」中注销账号。注销后无法登录，邮箱被释放（原邮箱可重新注册新账号），
          历史帖子和回应保留但统一显示为「已注销面具」，通知会被删除。
        </p>
      </section>

      <section>
        <h2 className="text-base font-semibold text-gray-900">图片处理</h2>
        <p>
          上传的图片会由服务器按方向校正、压缩并转换为 WebP，同时剥离 EXIF、GPS 等全部元数据。
          服务器会生成缩略图用于列表展示。
        </p>
      </section>
    </div>
  )
}
