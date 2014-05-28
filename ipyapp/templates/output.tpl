{% extends 'full.tpl' %}

{% block input_group -%}
{% endblock input_group %}

{%- block rawcell scoped -%}
{%- endblock rawcell -%}

{% block empty_in_prompt -%}
{%- endblock empty_in_prompt %}

{%- block header -%}
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8" />
<title>{{resources['metadata']['name']}}</title>

<script src="https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/2.0.3/jquery.min.js"></script>

{% for css in resources.inlining.css -%}
    <style type="text/css">
    {{ css }}
    </style>
{% endfor %}

<style type="text/css">
/* Overrides of notebook CSS for static HTML export */
body {
  overflow: visible;
  padding: 8px;
}

div#notebook {
  overflow: visible;
  border-top: none;
}

@media print {
  div.cell {
    display: block;
    page-break-inside: avoid;
  } 
  div.output_wrapper { 
    display: block;
    page-break-inside: avoid; 
  }
  div.output { 
    display: block;
    page-break-inside: avoid; 
  }
}
</style>

<!-- Loading mathjax macro -->
{{ mathjax() }}

<style type="text/css">
::selection{ background-color: #E13300; color: white; }
::moz-selection{ background-color: #E13300; color: white; }
::webkit-selection{ background-color: #E13300; color: white; }

body {
    font-family: "Helvetica Neue",Helvetica,Arial,"Lucida Grande",sans-serif;
    color: #888;
    font-style: normal;
    font-size: 14px;
    line-height: 22px;
}

a {
    color: #003399;
    background-color: transparent;
    font-weight: normal;
}

.title {
    padding: 0 20px;
    background: #32373a;
    position: relative;
    height: 50px;
}

.title h1 {
    color: #fff;
    margin: 0;
    font-size: 18px;
    font-weight: 400;
    line-height: 50px;
}

code {
    font-family: Consolas, Monaco, Courier New, Courier, monospace;
    font-size: 12px;
    background-color: #f9f9f9;
    border: 1px solid #D0D0D0;
    color: #002166;
    display: block;
    padding: 12px 10px 12px 10px;
}

#content {
    padding: 20px;
    zoom: 1;
}

#body{
    margin: 0 15px 0 15px;
}

p.footer{
    text-align: right;
    font-size: 11px;
    border-top: 1px solid #D0D0D0;
    line-height: 32px;
    padding: 0 10px 0 10px;
    margin: 20px 0 0 0;
}

#container{
    margin: 10px;
    border: 1px solid #D0D0D0;
    -webkit-box-shadow: 0 0 8px #D0D0D0;
}

div.prompt:empty {
    display: none;
}

div.output_area pre {
    font-size: 120%;
    color: #852121;
    line-height: 2em;
}

.rendered_html h1 {
    color: blue;
}
</style>

</head>
{%- endblock header -%}

{% block body %}
<body>
    <div id="container">
        <div class="title">
            <h1>IPython APP output, powered by conda launch</h1>
        </div>
        <div id="content">
            <div tabindex="-1" id="notebook" class="border-box-sizing">
                <div class="container" id="notebook-container">
                {{ super() }}
                </div>
            </div>
        </div>
    </div>
</body>
{%- endblock body %}



